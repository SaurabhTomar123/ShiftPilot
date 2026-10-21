"""Language shortcuts (architecture v3 sections 33-34, tasks B5.1 and B5.2).

    text -> model structured output -> Pydantic validation -> entity resolution -> deterministic preview

Nothing here writes. A command preview names the exact existing API call the UI makes on confirmation;
a rule preview is the rule validation service's preview. Ambiguous names ask "Which Ravi?" instead of
guessing. When the model is unavailable, the answer says so and the forms keep working.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.v2 import rules as rules_api
from api.v2 import schemas as s
from api.v2.errors import ApiError
from core.auth import Caller, Role, can_view_outlet
from db.models import Employee, Outlet
from db.models_v2 import Schedule
from db.session import tenant_session
from language import adapter, parsing
from scheduling import snapshot_db

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _managers_only(caller: Caller) -> None:
    if caller.role is Role.STAFF:
        raise ApiError("permission_denied", "Language shortcuts are for managers and owners.")


def _home(session: Session, caller: Caller, outlet_id: uuid.UUID | None) -> Outlet:
    wanted = outlet_id or (uuid.UUID(caller.outlet_id) if caller.outlet_id else None)
    outlet = (
        session.get(Outlet, wanted)
        if wanted
        else session.scalars(select(Outlet).order_by(Outlet.name)).first()
    )
    if outlet is None or not can_view_outlet(caller, str(outlet.id)):
        raise ApiError("permission_denied", "You can only use shortcuts for your outlet.")
    return outlet


def _staff(session: Session, caller: Caller) -> dict[uuid.UUID, list[str]]:
    rows = session.scalars(select(Employee).where(Employee.status == "active"))
    return {e.id: [e.name, *(e.aliases or [])] for e in rows if can_view_outlet(caller, str(e.outlet_id))}


Intent = Literal["give_time_off", "report_sick", "generate_week"]


def _name(intent: parsing.CommandIntent) -> Intent:
    assert intent.intent != "unsupported"  # unsupported intents never reach a preview
    return intent.intent


def _ask(intent: Intent | None, question: str, found: parsing.Resolution) -> s.CommandPreview:
    return s.CommandPreview(
        status="needs_clarification",
        intent=intent,
        summary=question,
        question=question,
        options=[s.CommandOption(employee_id=c.id, name=c.name) for c in found.matches],
    )


def _model_json(system: str, text: str) -> dict[str, object] | None:
    try:
        return adapter.current().complete_json(system, text)
    except adapter.LanguageUnavailable:
        return None


def parse_command(caller: Caller, body: s.CommandRequest) -> s.CommandPreview:
    _managers_only(caller)
    with tenant_session(caller) as session:
        home = _home(session, caller, body.outlet_id)
        tz = ZoneInfo(home.timezone)
        today = datetime.now(tz).date()
        raw = _model_json(
            parsing.COMMAND_PROMPT.format(today=today, weekday=WEEKDAYS[today.weekday()]), body.text
        )
        if raw is None:
            return s.CommandPreview(
                status="unavailable", summary="Language shortcuts are unavailable right now. Use the form."
            )
        intent = parsing.read(raw, parsing.CommandIntent)
        if not isinstance(intent, parsing.CommandIntent) or intent.intent == "unsupported":
            return s.CommandPreview(
                status="unsupported",
                summary="I can give someone a day off, record a sick day or generate a week. Try the form.",
            )
        if intent.intent == "generate_week":
            return _generate(session, caller, home, intent, today)
        return _absence(session, caller, intent, body, tz)


def _absence(
    session: Session, caller: Caller, intent: parsing.CommandIntent, body: s.CommandRequest, tz: ZoneInfo
) -> s.CommandPreview:
    staff = _staff(session, caller)
    if body.employee_id is not None:  # the answer to "Which Ravi?"
        if body.employee_id not in staff:
            raise ApiError("not_found", "Employee not found.")
        employee_id = body.employee_id
    else:
        query = intent.employee_query or ""
        found = parsing.resolve(query, staff) if query else parsing.Resolution("none", ())
        if found.kind == "many":
            return _ask(_name(intent), f"Which {query.split()[0]}?", found)
        if found.kind == "none":
            return _ask(
                _name(intent), f"Who did you mean by '{query}'?" if query else "Who is this for?", found
            )
        employee_id = found.matches[0].id
    if intent.day is None:
        return s.CommandPreview(
            status="needs_clarification", intent=_name(intent), summary="Which day?", question="Which day?"
        )
    employee = session.get(Employee, employee_id)
    assert employee is not None
    start = datetime(intent.day.year, intent.day.month, intent.day.day, tzinfo=tz)
    end = start + timedelta(days=1)
    affected = [r for r in snapshot_db.live_shifts(session, start, end, employee_ids=[employee_id])]
    kind = "leave" if intent.intent == "give_time_off" else "sick"
    what = "off" if kind == "leave" else "off sick"
    plural = "s" if len(affected) != 1 else ""
    cover = (
        f" {len(affected)} published shift{plural} will need cover; a repair starts after you confirm."
        if affected
        else " No published shift is affected."
    )
    day = f"{WEEKDAYS[intent.day.weekday()]} {intent.day:%d %b}"
    return s.CommandPreview(
        status="ready",
        intent=_name(intent),
        summary=f"Mark {employee.name} {what} on {day} ({kind}).{cover}",
        action=s.ProposedCall(
            operation_id="reportAbsence",
            method="POST",
            path="/v2/absences",
            body={
                "employee_id": str(employee_id),
                "start_at": start.isoformat(),
                "end_at": end.isoformat(),
                "kind": kind,
                "status": "confirmed",
                "reason": body.text,
            },
        ),
        affected_shift_count=len(affected),
    )


def _generate(
    session: Session, caller: Caller, home: Outlet, intent: parsing.CommandIntent, today: date
) -> s.CommandPreview:
    outlet = home
    if intent.outlet_query:
        names = {
            o.id: [o.name, o.slug]
            for o in session.scalars(select(Outlet))
            if can_view_outlet(caller, str(o.id))
        }
        found = parsing.resolve(intent.outlet_query, names)
        if found.kind != "one":
            return s.CommandPreview(
                status="needs_clarification",
                intent=_name(intent),
                summary="Which outlet?",
                question="Which outlet?",
            )
        picked = session.get(Outlet, found.matches[0].id)
        assert picked is not None
        outlet = picked
    week = intent.week_start or today - timedelta(days=today.weekday()) + timedelta(days=7)
    week -= timedelta(days=week.weekday())
    schedule = session.scalars(
        select(Schedule).where(Schedule.outlet_id == outlet.id, Schedule.week_start == week)
    ).first()
    base = schedule.current_version_id if schedule else None
    return s.CommandPreview(
        status="ready",
        intent="generate_week",
        summary=f"Generate schedule options for {outlet.name}, week of {week:%d %b}"
        + (" (the published week is kept until you approve a plan)." if base else "."),
        action=s.ProposedCall(
            operation_id="generateSchedule",
            method="POST",
            path=f"/v2/outlets/{outlet.id}/schedules/{week.isoformat()}/generate",
            body={
                "strategy": "balanced",
                "base_version_id": str(base) if base else None,
                "time_limit_seconds": 10,
            },
        ),
    )


def parse_rule(caller: Caller, body: s.RuleParseRequest) -> s.RuleParse:
    _managers_only(caller)
    with tenant_session(caller) as session:
        employees = list(session.scalars(select(Employee).where(Employee.status == "active")))
        tags = sorted({t for e in employees for t in (e.tags or ())})
        outlets = list(session.scalars(select(Outlet)))
        system = parsing.RULE_PROMPT.format(
            tags=", ".join(tags) or "none", outlets=", ".join(o.name for o in outlets)
        )
        raw = _model_json(system, body.text)
        if raw is None:
            return s.RuleParse(
                status="unavailable", message="Language shortcuts are unavailable right now. Use the form."
            )
        intent = parsing.read(raw, parsing.RuleIntent)
        if not isinstance(intent, parsing.RuleIntent) or not intent.supported or intent.rule_type is None:
            reason = intent.reason if isinstance(intent, parsing.RuleIntent) and intent.reason else ""
            return s.RuleParse(
                status="unsupported",
                message=f"That rule is not supported. {reason}".strip()
                + " Supported: latest end time, maximum days per week.",
            )
        level = intent.scope_level or "organization"
        query = intent.scope_query or ""
        scope: dict[str, str] = {}
        if level == "tag":
            tag = parsing.best_tag(query, set(tags))
            if tag is None:
                return s.RuleParse(
                    status="needs_clarification", message=f"No one is tagged '{query}'. Which group?"
                )
            scope = {"tag": tag}
        elif level == "outlet":
            found = parsing.resolve(query, {o.id: [o.name, o.slug] for o in outlets})
            if found.kind != "one":
                return s.RuleParse(status="needs_clarification", message="Which outlet?")
            scope = {"outlet_id": str(found.matches[0].id)}
        elif level == "employee":
            visible = {
                e.id: [e.name, *(e.aliases or [])]
                for e in employees
                if can_view_outlet(caller, str(e.outlet_id))
            }
            found = parsing.resolve(query, visible)
            if found.kind != "one":
                return s.RuleParse(
                    status="needs_clarification",
                    message=f"Which {query.split()[0] if query else 'person'}?",
                    options=[s.CommandOption(employee_id=c.id, name=c.name) for c in found.matches],
                )
            scope = {"employee_id": str(found.matches[0].id)}
        parameters: dict[str, object] = (
            {"latest_end_minute": intent.latest_end_minute, "weekdays": intent.weekdays or list(range(7))}
            if intent.rule_type == "max_shift_end_time"
            else {"days": intent.days}
        )
        definition = s.RuleDefinition(
            rule_type=intent.rule_type,
            scope_level=level,
            scope=scope,
            parameters=parameters,
            source_text=body.text,
        )
    preview = rules_api.preview(caller, definition)
    return s.RuleParse(status="ready", message=preview.summary, preview=preview)
