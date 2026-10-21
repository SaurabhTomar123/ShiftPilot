"""Scheduling rules: validation service, precedence and impact (architecture v3 section 21, B5.2).

    parse (language or form) -> schema validation -> scope resolution (who is affected)
    -> conflict analysis against active rules -> impact preview -> save

Conflicts are caught when a rule is written, not discovered later as solver infeasibility. Facts beat
rules: availability and absences are never overridden by a rule. Rules bind the next generation or
repair through the snapshot (scheduling.snapshot_db.effective_rules); published weeks are not changed.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.v2 import schemas as s
from api.v2.auth import require
from api.v2.errors import ApiError, not_found
from api.v2.service import _audit, idempotent
from core.auth import Caller, Role, can_view_outlet
from db.models import Employee, Outlet
from db.models_v2 import OutboxEvent, Schedule, SchedulingRule, VersionShift
from db.session import tenant_session
from scheduling import rules

IMPACT_LIMIT = 50


def _rule(d: s.RuleDefinition, rule_id: uuid.UUID | None = None) -> rules.Rule:
    return rules.Rule(
        rule_id or uuid.uuid4(),
        d.rule_type,
        d.scope_level,
        dict(d.scope),
        dict(d.parameters),
        d.hard,
        d.overrides_rule_id,
        d.source_text or "",
    )


def _stored(r: SchedulingRule) -> rules.Rule:
    return rules.Rule(
        r.id,
        r.rule_type,
        r.scope_level,
        r.scope,
        r.parameters,
        r.hard,
        r.overrides_rule_id,
        r.source_text or "",
    )


def _authorize(caller: Caller, d: s.RuleDefinition, session: Session) -> None:
    """Organization and tag rules reach every outlet: owners only. Managers set rules for their outlet
    or its employees."""
    require(caller, "manage_employees")
    if caller.role is Role.OWNER:
        return
    if d.scope_level in ("organization", "tag"):
        raise ApiError("permission_denied", "Only an owner can set organization-wide or tag rules.")
    if d.scope_level == "outlet" and not can_view_outlet(caller, d.scope.get("outlet_id", "")):
        raise ApiError("permission_denied", "You can only set rules for your outlet.")
    if d.scope_level == "employee":
        employee = session.get(Employee, _uuid(d.scope.get("employee_id")))
        if employee is None or not can_view_outlet(caller, str(employee.outlet_id)):
            raise ApiError("permission_denied", "You can only set rules for your outlet's employees.")


def _uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def _validate(session: Session, d: s.RuleDefinition) -> rules.Rule:
    rule = _rule(d)
    try:
        rules.check(rule)
    except rules.RuleError as exc:
        raise ApiError(
            "validation_failed",
            "Some fields need attention.",
            fields=[{"path": ["rule"], "message": str(exc)}],
        ) from exc
    target = {"outlet": Outlet, "employee": Employee}.get(d.scope_level)
    if target is not None:
        key = "outlet_id" if d.scope_level == "outlet" else "employee_id"
        if session.get(target, _uuid(d.scope.get(key))) is None:
            raise ApiError(
                "validation_failed",
                "Some fields need attention.",
                fields=[{"path": ["scope", key], "message": "Not found."}],
            )
    if d.overrides_rule_id is not None:
        base = session.get(SchedulingRule, d.overrides_rule_id)
        if base is None or base.status != "active" or base.rule_type != d.rule_type:
            raise ApiError(
                "validation_failed",
                "Some fields need attention.",
                fields=[
                    {"path": ["overrides_rule_id"], "message": "Must be an active rule of the same type."}
                ],
            )
    return rule


def _people(session: Session) -> list[rules.Person]:
    return [
        rules.Person(e.id, e.name, e.outlet_id, frozenset(e.tags or ()))
        for e in session.scalars(select(Employee).where(Employee.status == "active").order_by(Employee.name))
    ]


def _active(session: Session) -> list[rules.Rule]:
    return [
        _stored(r) for r in session.scalars(select(SchedulingRule).where(SchedulingRule.status == "active"))
    ]


def _impact(session: Session, rule: rules.Rule, affected: list[rules.Person]) -> list[s.RuleImpact]:
    ids = {p.id: p for p in affected}
    if not ids:
        return []
    tz_of = {o.id: ZoneInfo(o.timezone) for o in session.scalars(select(Outlet))}
    rows = session.scalars(
        select(VersionShift)
        .join(Schedule, Schedule.current_version_id == VersionShift.version_id)
        .where(VersionShift.employee_id.in_(ids), VersionShift.start_at >= datetime.now(UTC))
        .order_by(VersionShift.start_at)
    ).all()
    out: list[s.RuleImpact] = []
    if rule.rule_type == "max_shift_end_time":
        for r in rows:
            tz = tz_of[r.outlet_id]
            if rules.end_allowed([rule], r.start_at, r.end_at, tz) is not None:
                out.append(_impact_row(r, ids, tz, f"Ends at {r.end_at.astimezone(tz):%H:%M}"))
    else:
        weeks: dict[tuple[uuid.UUID, Any], list[VersionShift]] = defaultdict(list)
        for r in rows:
            local = r.start_at.astimezone(tz_of[r.outlet_id]).date()
            weeks[r.employee_id, local.isocalendar()[:2]].append(r)  # type: ignore[index]
        for shifts in weeks.values():
            tz = tz_of[shifts[0].outlet_id]
            days = sorted({sh.start_at.astimezone(tz).date() for sh in shifts})
            if len(days) > rule.parameters["days"]:
                last = [sh for sh in shifts if sh.start_at.astimezone(tz).date() == days[-1]][0]
                out.append(_impact_row(last, ids, tz, f"{len(days)} working days that week"))
    return out[:IMPACT_LIMIT]


def _impact_row(
    r: VersionShift, ids: dict[uuid.UUID, rules.Person], tz: ZoneInfo, message: str
) -> s.RuleImpact:
    assert r.employee_id is not None
    return s.RuleImpact(
        employee_id=r.employee_id,
        name=ids[r.employee_id].name,
        logical_shift_id=r.logical_shift_id,
        start_at=r.start_at.astimezone(tz),
        end_at=r.end_at.astimezone(tz),
        message=message,
    )


def _preview(session: Session, d: s.RuleDefinition) -> s.RulePreview:
    rule = _validate(session, d)
    people = _people(session)
    affected = [p for p in people if rules.applies(rule, p)]
    by_name = {p.name: p for p in people}
    conflicts = []
    for c in rules.conflicts(rule, _active(session), people):
        suggestion = None
        if len(c.people) == 1:
            person = by_name[c.people[0]]
            suggestion = d.model_copy(
                update={
                    "scope_level": "employee",
                    "scope": {"employee_id": str(person.id)},
                    "overrides_rule_id": c.rule_id,
                }
            )
        conflicts.append(
            s.RuleConflict(
                rule_id=c.rule_id,
                rule_name=c.rule_name,
                employees=list(c.people),
                message=c.message,
                suggested_exception=suggestion,
            )
        )
    return s.RulePreview(
        rule=d,
        summary=rules.describe(rule),
        valid=not conflicts,
        affected=[s.RuleEmployee(employee_id=p.id, name=p.name) for p in affected],
        conflicts=conflicts,
        impact=_impact(session, rule, affected),
    )


def preview(caller: Caller, d: s.RuleDefinition) -> s.RulePreview:
    with tenant_session(caller) as session:
        _authorize(caller, d, session)
        return _preview(session, d)


def _view(r: SchedulingRule) -> s.SchedulingRule:
    return s.SchedulingRule(
        id=r.id,
        rule_type=r.rule_type,  # type: ignore[arg-type]
        scope_level=r.scope_level,  # type: ignore[arg-type]
        scope={k: str(v) for k, v in r.scope.items()},
        parameters=r.parameters,
        hard=r.hard,
        overrides_rule_id=r.overrides_rule_id,
        source_text=r.source_text,
        summary=rules.describe(_stored(r)),
        status=r.status,  # type: ignore[arg-type]
        created_at=r.created_at,
    )


def _changed(session: Session, r: SchedulingRule) -> None:
    session.add(
        OutboxEvent(
            id=uuid.uuid7(),
            org_id=r.org_id,
            topic="rule.changed",
            aggregate_type="scheduling_rule",
            aggregate_id=r.id,
            payload={"rule_id": str(r.id), "status": r.status},
        )
    )


def create(caller: Caller, key: str, d: s.RuleDefinition) -> s.SchedulingRule:
    with tenant_session(caller) as session:
        _authorize(caller, d, session)

        def produce() -> s.SchedulingRule:
            found = _preview(session, d)
            if found.conflicts:
                raise ApiError(
                    "conflict",
                    found.conflicts[0].message,
                    conflicts=[c.model_dump(mode="json") for c in found.conflicts],
                )
            row = SchedulingRule(
                id=uuid.uuid7(),
                org_id=uuid.UUID(caller.org_id),
                scope_level=d.scope_level,
                scope=dict(d.scope),
                rule_type=d.rule_type,
                parameters=dict(d.parameters),
                hard=d.hard,
                overrides_rule_id=d.overrides_rule_id,
                source_text=d.source_text,
                status="active",
                created_by_user_id=uuid.UUID(caller.user_id),
                revision=1,
            )
            session.add(row)
            session.flush()
            session.refresh(row)
            _audit(session, caller, "RULE_CREATED", "scheduling_rule", row.id, None, None)
            _changed(session, row)
            return _view(row)

        return s.SchedulingRule.model_validate(idempotent(session, caller, key, "createRule", d, produce))


def list_rules(caller: Caller, include_archived: bool) -> s.RuleList:
    require(caller, "manage_employees")
    with tenant_session(caller) as session:
        query = select(SchedulingRule).order_by(SchedulingRule.created_at)
        if not include_archived:
            query = query.where(SchedulingRule.status != "archived")
        return s.RuleList(items=[_view(r) for r in session.scalars(query)])


def archive(caller: Caller, rule_id: uuid.UUID) -> s.SchedulingRule:
    with tenant_session(caller) as session:
        row = session.scalars(
            select(SchedulingRule).where(SchedulingRule.id == rule_id).with_for_update()
        ).first()
        if row is None:
            raise not_found("Rule")
        _authorize(caller, _view(row), session)
        if row.status != "archived":
            row.status = "archived"
            session.flush()
            _audit(session, caller, "RULE_ARCHIVED", "scheduling_rule", row.id, None, None)
            _changed(session, row)
        return _view(row)
