"""Scenario Lab overlays (architecture v4 sections 23, 42). Pure.

A scenario is a list of hypothetical events applied while building the solver input. Nothing here (or
anywhere a scenario runs) writes absences, availability, rules or staffing requirements: isolation is
enforced by this module being the only place events take effect, on an in-memory Snapshot.

Event types (version 1; anything else is refused, never turned into free-form solver code):

    demand_change   {percent, skill_id?, weekdays?, start_minute?, end_minute?}
                    minimum and preferred staffing scaled by (100 + percent)%, rounded up
    absence         {employee_id, start_at, end_at}            a hypothetical confirmed absence
    outlet_closure  {day}                                       no demand and no shifts that local day
    labour_cap      {max_cost_paise}                            hard ceiling on labour + overtime premium
    rule            {rule_type, parameters, employee_ids}       a hypothetical rule for these people
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Any

from scheduling import rules
from scheduling.model import Absence, Shift, Snapshot

EVENT_TYPES = ("demand_change", "absence", "outlet_closure", "labour_cap", "rule")
NS = uuid.UUID("5c3d1f0e-7b8a-4f2e-9a61-0d4e8c2b7f13")


class EventError(ValueError):
    """An event the Scenario Lab cannot apply; the message names the field."""

    def __init__(self, path: list[str | int], message: str) -> None:
        super().__init__(message)
        self.path = path


@dataclass(frozen=True)
class Event:
    type: str
    payload: dict[str, Any]


def _uuid(payload: dict[str, Any], key: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(payload[key]))
    except KeyError, ValueError:
        raise EventError(["payload", key], f"{key} must be an id.") from None


def _int(payload: dict[str, Any], key: str, lo: int, hi: int, default: int | None = None) -> int:
    value = payload.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or not lo <= value <= hi:
        raise EventError(["payload", key], f"{key} must be a whole number from {lo} to {hi}.")
    return value


def _time(payload: dict[str, Any], key: str) -> datetime:
    try:
        value = datetime.fromisoformat(str(payload[key]))
    except KeyError, ValueError:
        raise EventError(["payload", key], f"{key} must be a date-time with an offset.") from None
    if value.tzinfo is None:
        raise EventError(["payload", key], f"{key} must include a UTC offset.")
    return value


def check(snap: Snapshot, event: Event) -> None:
    """Validate one event against the scenario's snapshot (people and skills must exist)."""
    p = event.payload
    if event.type not in EVENT_TYPES:
        raise EventError(["type"], f"Unsupported scenario event. Supported: {', '.join(EVENT_TYPES)}.")
    if event.type == "demand_change":
        _int(p, "percent", -100, 300)
        if p.get("skill_id") is not None and _uuid(p, "skill_id") not in snap.skill_names:
            raise EventError(["payload", "skill_id"], "Unknown skill.")
        weekdays = p.get("weekdays", list(range(7)))
        if not isinstance(weekdays, list) or not weekdays or any(d not in range(7) for d in weekdays):
            raise EventError(["payload", "weekdays"], "weekdays must list days 0 (Monday) to 6 (Sunday).")
        if _int(p, "start_minute", 0, 1440, 0) >= _int(p, "end_minute", 0, 2880, 2880):
            raise EventError(["payload", "end_minute"], "end_minute must be after start_minute.")
    elif event.type == "absence":
        if _uuid(p, "employee_id") not in snap.employees:
            raise EventError(["payload", "employee_id"], "Unknown employee.")
        if _time(p, "end_at") <= _time(p, "start_at"):
            raise EventError(["payload", "end_at"], "end_at must be after start_at.")
    elif event.type == "outlet_closure":
        day = _day(p)
        start, end = snap.week_bounds()
        if not start.date() <= day < end.date():
            raise EventError(["payload", "day"], "The day must be in the scenario's week.")
    elif event.type == "labour_cap":
        _int(p, "max_cost_paise", 0, 10**12)
    elif event.type == "rule":
        ids = p.get("employee_ids")
        if not isinstance(ids, list) or not ids:
            raise EventError(["payload", "employee_ids"], "List the people the rule applies to.")
        for i, raw in enumerate(ids):
            try:
                known = uuid.UUID(str(raw)) in snap.employees
            except ValueError:
                known = False
            if not known:
                raise EventError(["payload", "employee_ids", i], "Unknown employee.")
        try:
            rules.check(_rule(p, 0, str(ids[0])))
        except rules.RuleError as exc:
            raise EventError(["payload", "parameters"], str(exc)) from None


def _day(p: dict[str, Any]) -> date:
    try:
        return date.fromisoformat(str(p["day"]))
    except KeyError, ValueError:
        raise EventError(["payload", "day"], "day must be a date (YYYY-MM-DD).") from None


def _rule(p: dict[str, Any], sequence: int, employee: str) -> rules.Rule:
    """The hypothetical rule for one person, shaped exactly like a real employee-level rule."""
    return rules.Rule(
        uuid.uuid5(NS, f"scenario-rule:{sequence}:{p.get('rule_type')}:{employee}"),
        str(p.get("rule_type")),
        "employee",
        {"employee_id": employee},
        dict(p.get("parameters") or {}),
        True,
        None,
        "Scenario rule",
    )


def _scaled(value: int, percent: int) -> int:
    return max(0, -(-value * (100 + percent) // 100))  # ceiling division


def _demand(snap: Snapshot, p: dict[str, Any]) -> Snapshot:
    tz = snap.outlet.tz
    skill = uuid.UUID(str(p["skill_id"])) if p.get("skill_id") else None
    weekdays = set(p.get("weekdays", range(7)))
    lo, hi, percent = p.get("start_minute", 0), p.get("end_minute", 2880), int(p["percent"])
    reqs = []
    for r in snap.requirements:
        local = r.interval_start.astimezone(tz)
        if (
            r.outlet_id == snap.outlet_id
            and (skill is None or r.skill_id == skill)
            and local.weekday() in weekdays
            and lo <= local.hour * 60 + local.minute < hi
        ):
            low = _scaled(r.minimum, percent)
            r = replace(r, minimum=low, preferred=max(low, _scaled(r.preferred, percent)))
        reqs.append(r)
    return replace(snap, requirements=tuple(reqs))


def _absence(snap: Snapshot, p: dict[str, Any]) -> Snapshot:
    hypothetical = Absence(_uuid(p, "employee_id"), _time(p, "start_at"), _time(p, "end_at"), "confirmed")
    return replace(snap, absences=(*snap.absences, hypothetical))


def _closure(snap: Snapshot, p: dict[str, Any]) -> Snapshot:
    tz, day = snap.outlet.tz, _day(p)

    def open_on(start: datetime) -> bool:
        return start.astimezone(tz).date() != day

    closed = {sh.logical_id for sh in snap.base if not open_on(sh.start_at)}
    return replace(
        snap,
        requirements=tuple(
            r for r in snap.requirements if r.outlet_id != snap.outlet_id or open_on(r.interval_start)
        ),
        base=tuple(sh for sh in snap.base if open_on(sh.start_at)),
        base_locked={k: sh for k, sh in snap.base_locked.items() if open_on(sh.start_at)},
        frozen=frozenset(k for k in snap.frozen if k not in closed),
        closed_days=frozenset({*snap.closed_days, day}),
    )


def _cap(snap: Snapshot, p: dict[str, Any]) -> Snapshot:
    cap = int(p["max_cost_paise"])
    current = snap.labour_cap_paise
    return replace(snap, labour_cap_paise=cap if current is None else min(cap, current))


def _extra_rule(snap: Snapshot, p: dict[str, Any], n: int) -> Snapshot:
    added = {uuid.UUID(str(i)): _rule(p, n, str(i)) for i in p["employee_ids"]}
    return replace(snap, rules={**snap.rules, **{e: (*snap.rules.get(e, ()), r) for e, r in added.items()}})


def apply(snap: Snapshot, events: list[Event]) -> Snapshot:
    """The snapshot as it would be if every event happened, in sequence order."""
    for n, event in enumerate(events):
        check(snap, event)
        p = event.payload
        if event.type == "demand_change":
            snap = _demand(snap, p)
        elif event.type == "absence":
            snap = _absence(snap, p)
        elif event.type == "outlet_closure":
            snap = _closure(snap, p)
        elif event.type == "labour_cap":
            snap = _cap(snap, p)
        elif event.type == "rule":
            snap = _extra_rule(snap, p, n)
    return snap


def baseline(snap: Snapshot, roster: list[Shift]) -> list[Shift]:
    """The current plan as it stands under the scenario: shifts on a closed day are gone."""
    tz = snap.outlet.tz
    return [sh for sh in roster if sh.start_at.astimezone(tz).date() not in snap.closed_days]
