"""Build contracts/v2 from api.v2: openapi.json plus synthetic fixtures.

    python -m api.v2.contract_build           # (re)write contracts/v2
    python -m api.v2.contract_build --check   # exit 1 if contracts/v2 is out of date

Fixtures are synthetic and deterministic. Every body is constructed through its pydantic model, so
building them validates them. Roster metrics are computed from the generated shifts (not typed in)
so numbers in one fixture agree with each other. The fixture roster is built by a simple
rule-respecting greedy pass; it is illustrative data, not solver output.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI
from pydantic import BaseModel

from api.v2 import schemas as s
from api.v2.routes import router

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "contracts" / "v2"
NS = uuid.UUID("6f1c0a52-4b7e-4c51-9f3e-2b9d6c1e7a10")
IST = timezone(timedelta(hours=5, minutes=30))
TZ = "Asia/Kolkata"
WEEK = date(2026, 10, 19)  # published week
NEXT_WEEK = date(2026, 10, 26)  # empty week used for generation
INTERVAL = 30


def uid(kind: str, key: str) -> uuid.UUID:
    return uuid.uuid5(NS, f"{kind}:{key}")


def at(day: date, minute: int) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=IST) + timedelta(minutes=minute)


def stamp(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=IST)


# ---------------------------------------------------------------- reference data

ORG = uid("org", "spice-route")
OUTLETS = [("indiranagar", "Indiranagar"), ("koramangala", "Koramangala"), ("hsr", "HSR Layout")]
SKILLS = ["Grill", "Prep", "Server", "Cashier", "Barista"]
SKILL = {name: uid("skill", name) for name in SKILLS}
HOME = uid("outlet", "indiranagar")
OPEN, CLOSE = 600, 1380  # 10:00-23:00 every day at Indiranagar


@dataclass(frozen=True)
class Emp:
    key: str
    name: str
    skills: tuple[str, ...]
    rate_rupees: int  # divisible by 3 so per-minute paise is exact
    unavailable_days: tuple[int, ...] = ()
    latest_end: int | None = None  # weekday availability end (students)
    tags: tuple[str, ...] = ()
    preferred: tuple[int, int] | None = None  # preferred window (start, end) every day


EMPLOYEES = [
    Emp("ravi", "Ravi Kumar", ("Grill", "Prep"), 210, unavailable_days=(1, 6)),
    Emp("arjun", "Arjun Rao", ("Grill",), 195),
    Emp("neha", "Neha Iyer", ("Grill", "Prep"), 204, unavailable_days=(2,)),
    Emp("aman", "Aman Shah", ("Prep", "Grill"), 180),
    Emp("kavya", "Kavya Reddy", ("Grill", "Prep"), 189, preferred=(600, 1080)),
    Emp("priya", "Priya Sharma", ("Server", "Cashier"), 174, preferred=(600, 1080)),
    Emp("karan", "Karan Mehta", ("Server",), 165),
    Emp("divya", "Divya Nair", ("Server", "Cashier"), 171),
    Emp("farhan", "Farhan Ali", ("Server",), 165),
    Emp("meera", "Meera Pillai", ("Cashier", "Server"), 168),
    Emp("sanjay", "Sanjay Gowda", ("Server", "Barista"), 171),
    Emp("anjali", "Anjali Rao", ("Cashier",), 162),
    Emp("rohit", "Rohit Verma", ("Server",), 150, latest_end=1260, tags=("student",)),
]
KORAMANGALA_STAFF = [
    Emp("suresh", "Suresh Pillai", ("Grill", "Prep"), 207),
    Emp("lakshmi", "Lakshmi Menon", ("Grill",), 198, unavailable_days=(0,)),
    Emp("imran", "Imran Khan", ("Grill", "Prep"), 201),
    Emp("pooja", "Pooja Desai", ("Prep", "Grill"), 183, unavailable_days=(6,)),
    Emp("vivek", "Vivek Joshi", ("Grill", "Prep"), 192),
    Emp("ananya", "Ananya Bose", ("Server", "Cashier"), 177, preferred=(600, 1080)),
    Emp("rahul", "Rahul Sinha", ("Server",), 168),
    Emp("sneha", "Sneha Kulkarni", ("Server", "Cashier"), 174),
    Emp("tarun", "Tarun Bhat", ("Server",), 165, unavailable_days=(2,)),
    Emp("fatima", "Fatima Shaikh", ("Cashier", "Server"), 171),
    Emp("nikhil", "Nikhil Rao", ("Server", "Barista"), 168),
    Emp("deepa", "Deepa Hegde", ("Cashier",), 159),
    Emp("kabir", "Kabir Malhotra", ("Server",), 150, latest_end=1260, tags=("student",)),
]
HSR_STAFF = [
    Emp("mohan", "Mohan Reddy", ("Grill", "Prep"), 204),
    Emp("gayatri", "Gayatri Iyer", ("Grill",), 195),
    Emp("joseph", "Joseph Mathew", ("Grill", "Prep"), 198, unavailable_days=(3,)),
    Emp("swati", "Swati Nair", ("Prep", "Grill"), 180),
    Emp("harish", "Harish Gowda", ("Grill", "Prep"), 189, preferred=(600, 1080)),
    Emp("ishita", "Ishita Sen", ("Server", "Cashier"), 174),
    Emp("manoj", "Manoj Patil", ("Server",), 162),
    Emp("ritu", "Ritu Agarwal", ("Server", "Cashier"), 171, unavailable_days=(5,)),
    Emp("sameer", "Sameer Qureshi", ("Server",), 165),
    Emp("zoya", "Zoya Mirza", ("Cashier", "Server"), 168),
    Emp("ajay", "Ajay Kumar", ("Server", "Barista"), 171),
    Emp("bhavna", "Bhavna Shah", ("Cashier",), 162),
    Emp("yash", "Yash Chawla", ("Server",), 150, latest_end=1260, tags=("student",)),
]
STAFF = {"indiranagar": EMPLOYEES, "koramangala": KORAMANGALA_STAFF, "hsr": HSR_STAFF}
EMP = {e.key: e for staff in STAFF.values() for e in staff}


@dataclass(frozen=True)
class Template:
    key: str
    start: int
    end: int
    break_start: int | None  # 30-minute unpaid break


TEMPLATES = {
    "open": Template("open", 600, 1080, 930),  # 10:00-18:00, break 15:30
    "close": Template("close", 900, 1380, 1020),  # 15:00-23:00, break 17:00
    "dinner": Template("dinner", 1080, 1380, None),  # 18:00-23:00
}


def slots_for(day: date, *, with_preferred_extras: bool) -> list[tuple[str, str]]:
    """(skill, template) shifts to staff on one day."""
    slots = [
        ("Grill", "open"),
        ("Grill", "close"),
        ("Prep", "open"),
        ("Server", "open"),
        ("Server", "close"),
        ("Server", "dinner"),
        ("Cashier", "open"),
        ("Cashier", "close"),
    ]
    if with_preferred_extras and day.weekday() in (4, 5):  # Fri/Sat dinner rush
        slots += [("Grill", "dinner"), ("Server", "dinner")]
    return slots


def requirement(skill: str, weekday: int, minute: int) -> tuple[int, int]:
    """(minimum, preferred) staff for the 30-minute interval starting at `minute`."""
    dinner = 1080 <= minute < 1320
    lunch = 720 <= minute < 900
    rush = weekday in (4, 5)
    if skill == "Grill":
        return (1, 2 if (dinner or lunch) else 1) if not (dinner and rush) else (1, 3)
    if skill == "Prep":
        return (0, 1) if minute < 1080 else (0, 0)
    if skill == "Server":
        if dinner:
            return (2, 4 if rush else 3)
        return (1, 2 if lunch else 1)
    if skill == "Cashier":
        return (1, 2 if (dinner and rush) else 1)
    return (0, 0)


# ---------------------------------------------------------------- roster construction


@dataclass(frozen=True)
class PlannedShift:
    key: str
    day: date
    skill: str
    template: Template
    employee: str | None


def available(e: Emp, day: date, t: Template) -> bool:
    if day.weekday() in e.unavailable_days:
        return False
    return not (e.latest_end is not None and day.weekday() < 5 and t.end > e.latest_end)


def build_roster(
    week: date, *, with_preferred_extras: bool, staff: list[Emp] = EMPLOYEES
) -> list[PlannedShift]:
    shifts: list[PlannedShift] = []
    count: dict[str, int] = defaultdict(int)
    last_end: dict[str, datetime] = {}
    for d in range(7):
        day = week + timedelta(days=d)
        busy: set[str] = set()
        # Fill the most constrained skills first so specialists are not used up elsewhere.
        slots = sorted(
            slots_for(day, with_preferred_extras=with_preferred_extras),
            key=lambda st: sum(st[0] in e.skills for e in staff),
        )
        for i, (skill, tkey) in enumerate(slots):
            t = TEMPLATES[tkey]
            ok = [
                e
                for e in staff
                if skill in e.skills
                and e.key not in busy
                and count[e.key] < 5
                and available(e, day, t)
                and (e.key not in last_end or at(day, t.start) - last_end[e.key] >= timedelta(hours=10))
            ]
            if not ok:
                raise RuntimeError(f"fixture roster: nobody for {skill}/{tkey} on {day}")
            pick = min(ok, key=lambda e: (count[e.key], len(e.skills), e.key))
            busy.add(pick.key)
            count[pick.key] += 1
            last_end[pick.key] = at(day, t.end)
            shifts.append(PlannedShift(f"{week}:{day}:{i}:{skill}:{tkey}", day, skill, t, pick.key))
    return shifts


def paid_minutes(t: Template) -> int:
    return t.end - t.start - (30 if t.break_start is not None else 0)


def rate_paise_per_minute(e: Emp) -> int:
    return e.rate_rupees * 100 // 60


def evaluate(
    week: date, roster: list[PlannedShift]
) -> tuple[s.Metrics, list[s.CoverageCell], s.ValidationResult]:
    cells: list[s.CoverageCell] = []
    covered = target = min_deficit = pref_deficit = 0
    soft: list[s.Violation] = []
    for d in range(7):
        day = week + timedelta(days=d)
        for skill in ["Grill", "Prep", "Server", "Cashier"]:
            day_pref_deficit = 0
            for minute in range(OPEN, CLOSE, INTERVAL):
                mn, pref = requirement(skill, day.weekday(), minute)
                on = sum(
                    1
                    for sh in roster
                    if sh.day == day
                    and sh.skill == skill
                    and sh.employee
                    and sh.template.start <= minute < sh.template.end
                    and not (
                        sh.template.break_start is not None
                        and sh.template.break_start <= minute < sh.template.break_start + 30
                    )
                )
                cells.append(
                    s.CoverageCell(
                        skill_id=SKILL[skill],
                        interval_start=at(day, minute),
                        minimum_required=mn,
                        preferred_required=pref,
                        scheduled=on,
                    )
                )
                covered += min(on, pref) * INTERVAL
                target += pref * INTERVAL
                min_deficit += max(0, mn - on) * INTERVAL
                day_pref_deficit += max(0, pref - on) * INTERVAL
            pref_deficit += day_pref_deficit
            if day_pref_deficit:
                soft.append(
                    s.Violation(
                        code="preferred_coverage",
                        severity="soft",
                        employee_id=None,
                        logical_shift_ids=[],
                        message=f"{skill} is below preferred staffing for {day_pref_deficit} staff-minutes "
                        f"on {day:%a %d %b}.",
                        facts={
                            "date": day.isoformat(),
                            "skill_id": str(SKILL[skill]),
                            "deficit_minutes": day_pref_deficit,
                        },
                    )
                )
    if min_deficit:
        raise RuntimeError("fixture roster violates a hard minimum; fix the generator")
    assigned = [sh for sh in roster if sh.employee]
    cost = sum(
        paid_minutes(sh.template) * rate_paise_per_minute(EMP[sh.employee]) for sh in assigned if sh.employee
    )
    prefs = [sh for sh in assigned if sh.employee and EMP[sh.employee].preferred]
    inside = [
        sh
        for sh in prefs
        if sh.employee
        and (p := EMP[sh.employee].preferred)
        and p[0] <= sh.template.start
        and sh.template.end <= p[1]
    ]
    metrics = s.Metrics(
        coverage_ratio=round(covered / target, 4) if target else None,
        minimum_deficit_minutes=min_deficit,
        preferred_deficit_minutes=pref_deficit,
        labour_cost=s.Money(amount_paise=cost),
        overtime_cost=s.Money(amount_paise=0),
        overtime_minutes=0,
        preference_match_ratio=round(len(inside) / len(prefs), 4) if prefs else None,
        open_shifts=sum(1 for sh in roster if sh.employee is None),
        assigned_minutes=sum(paid_minutes(sh.template) for sh in assigned),
    )
    return metrics, cells, s.ValidationResult(hard_violations=0, soft_violations=len(soft), violations=soft)


def to_shifts(version_key: str, roster: list[PlannedShift], outlet_id: uuid.UUID = HOME) -> list[s.Shift]:
    out = []
    for sh in roster:
        t = sh.template
        out.append(
            s.Shift(
                id=uid("version_shift", f"{version_key}:{sh.key}"),
                logical_shift_id=uid(
                    "logical_shift", sh.key if outlet_id == HOME else f"{outlet_id}:{sh.key}"
                ),
                outlet_id=outlet_id,
                employee_id=uid("employee", sh.employee) if sh.employee else None,
                skill_id=SKILL[sh.skill],
                start_at=at(sh.day, t.start),
                end_at=at(sh.day, t.end),
                break_start_at=at(sh.day, t.break_start) if t.break_start is not None else None,
                break_minutes=30 if t.break_start is not None else 0,
                locked=(sh.employee == "ravi" and sh.day.weekday() == 5),
                lock_reason="Locked by manager"
                if (sh.employee == "ravi" and sh.day.weekday() == 5)
                else None,
            )
        )
    return out


def version(
    key: str, week: date, roster: list[PlannedShift], *, outlet_key: str = "indiranagar", **summary: Any
) -> s.ScheduleVersion:
    metrics, cells, validation = evaluate(week, roster)
    return s.ScheduleVersion(
        id=uid("version", key),
        schedule_id=uid("schedule", f"{outlet_key}:{week}"),
        input_hash="sha256:" + uuid.uuid5(NS, f"input:{key}").hex,
        shifts=to_shifts(key, roster, uid("outlet", outlet_key)),
        metrics=metrics,
        coverage=cells,
        validation=validation,
        **summary,
    )


# ---------------------------------------------------------------- fixture bodies

PERSONAS: dict[str, tuple[str, s.Role, uuid.UUID | None, uuid.UUID | None]] = {
    "owner": ("Asha Menon", "owner", None, None),
    "manager_indiranagar": ("Vikram Das", "manager", HOME, None),
    "staff_ravi": ("Ravi Kumar", "staff", HOME, uid("employee", "ravi")),
}


def me(persona: str) -> s.Me:
    name, role, outlet, employee = PERSONAS[persona]
    return s.Me(
        user_id=uid("user", persona),
        org_id=ORG,
        org_name="Spice Route Kitchens",
        display_name=name,
        role=role,
        outlet_id=outlet,
        employee_id=employee,
        timezone=TZ,
        capabilities=CAPABILITIES[role],
    )


CAPABILITIES: dict[str, list[s.Capability]] = {
    "owner": [
        "view_all_outlets",
        "manage_employees",
        "edit_demand",
        "generate",
        "publish",
        "view_costs",
        "approve_cross_outlet",
    ],
    "manager": ["manage_employees", "edit_demand", "generate", "publish", "view_costs"],
    "staff": ["view_own_schedule", "report_own_absence"],
}


def roster_employees(
    v: s.ScheduleVersion | None, staff: list[Emp] = EMPLOYEES, home: uuid.UUID = HOME
) -> list[s.RosterEmployee]:
    def paid(sh: s.Shift) -> int:
        return int((sh.end_at - sh.start_at).total_seconds() // 60) - sh.break_minutes

    shifts = v.shifts if v else []
    return [
        s.RosterEmployee(
            id=uid("employee", e.key),
            name=e.name,
            home_outlet_id=home,
            skill_ids=[SKILL[k] for k in e.skills],
            status="active",
            scheduled_minutes=sum(paid(sh) for sh in shifts if sh.employee_id == uid("employee", e.key)),
            regular_weekly_minutes=2880,
            max_weekly_minutes=2880,
        )
        for e in staff
    ]


def requested_leave(v: s.ScheduleVersion, day: date) -> list[s.AbsenceMark]:
    """A pending leave request on a day the employee is off, so it creates no conflict."""
    working = {sh.employee_id for sh in v.shifts if sh.start_at.date() == day}
    off = next(e for e in EMPLOYEES if uid("employee", e.key) not in working)
    return [
        s.AbsenceMark(
            id=uid("absence", f"{off.key}:{day}"),
            employee_id=uid("employee", off.key),
            start_at=at(day, 0),
            end_at=at(day, 1440),
            kind="leave",
            status="requested",
        )
    ]


def outlet(key: str, name: str) -> s.Outlet:
    hours = [s.OperatingWindow(weekday=d, open_minute=OPEN, close_minute=CLOSE) for d in range(7)]
    return s.Outlet(id=uid("outlet", key), name=name, slug=key, timezone=TZ, operating_hours=hours)


def employee(e: Emp, home: uuid.UUID = HOME) -> s.Employee:
    return s.Employee(
        id=uid("employee", e.key),
        name=e.name,
        home_outlet_id=home,
        status="active",
        hourly_rate=s.Money(amount_paise=e.rate_rupees * 100),
        skills=[s.EmployeeSkill(skill_id=SKILL[k], level=2 if i == 0 else 1) for i, k in enumerate(e.skills)],
        tags=list(e.tags),
        regular_weekly_minutes=2880,
        max_weekly_minutes=2880,
        preferred_weekly_minutes=2250 if e.preferred else None,
        overtime_allowed=False,
        cross_outlet_eligible=e.key in ("arjun", "divya"),
        revision=1,
    )


def availability(e: Emp) -> s.Availability:
    windows = []
    for d in range(7):
        if d in e.unavailable_days:
            windows.append(
                s.AvailabilityWindow(weekday=d, start_minute=0, end_minute=1440, kind="unavailable")
            )
            continue
        end = e.latest_end if (e.latest_end is not None and d < 5) else CLOSE
        windows.append(s.AvailabilityWindow(weekday=d, start_minute=OPEN, end_minute=end, kind="available"))
        if e.preferred:
            windows.append(
                s.AvailabilityWindow(
                    weekday=d, start_minute=e.preferred[0], end_minute=e.preferred[1], kind="preferred"
                )
            )
    return s.Availability(employee_id=uid("employee", e.key), windows=windows, revision=1)


def staffing(week: date) -> s.StaffingRequirements:
    items = []
    for d in range(7):
        day = week + timedelta(days=d)
        for skill in ["Grill", "Prep", "Server", "Cashier"]:
            for minute in range(OPEN, CLOSE, INTERVAL):
                mn, pref = requirement(skill, day.weekday(), minute)
                if pref:
                    items.append(
                        s.StaffingInterval(
                            skill_id=SKILL[skill],
                            interval_start=at(day, minute),
                            interval_end=at(day, minute + INTERVAL),
                            minimum_required=mn,
                            preferred_required=pref,
                            source="band",
                        )
                    )
    return s.StaffingRequirements(
        outlet_id=HOME, week_start=week, interval_minutes=INTERVAL, demand_revision=3, intervals=items
    )


def error(code: s.ErrorCode, message: str, *, retryable: bool = False, **details: Any) -> s.ErrorResponse:
    return s.ErrorResponse(
        error=s.ErrorBody(
            code=code,
            message=message,
            retryable=retryable,
            details=details,
        )
    )


def run(state: str, **kw: Any) -> s.OptimizationRun:
    base: dict[str, Any] = dict(
        id=uid("run", f"generate:{NEXT_WEEK}"),
        kind="generate",
        outlet_ids=[HOME],
        base_version_ids=[],
        strategy="balanced",
        job_state=state,
        solver_status=None,
        input_hash="sha256:" + uuid.uuid5(NS, "input:run").hex,
        queued_at=stamp("2026-10-18T19:40:00"),
        started_at=None,
        finished_at=None,
        solver_wall_ms=None,
        poll_after_ms=500,
        candidates=[],
        infeasibility=None,
        error=None,
    )
    base.update(kw)
    return s.OptimizationRun(**base)


@dataclass(frozen=True)
class Fixture:
    name: str
    operation_id: str
    method: str
    path: str
    persona: str | None
    status: int
    body: BaseModel | None  # None only for bodiless responses such as 304
    request: dict[str, Any] | None = None
    headers: dict[str, str] | None = None  # response headers the consumer relies on

    @property
    def schema(self) -> str | None:
        return type(self.body).__name__ if self.body is not None else None

    def to_json(self) -> dict[str, Any]:
        response: dict[str, Any] = {"status": self.status, "schema": self.schema}
        if self.headers:
            response["headers"] = self.headers
        response["body"] = self.body.model_dump(mode="json") if self.body is not None else None
        return {
            "name": self.name,
            "operation_id": self.operation_id,
            "method": self.method,
            "path": self.path,
            "persona": self.persona,
            "request": self.request or {},
            "response": response,
        }


def fixtures() -> list[Fixture]:
    ind = str(HOME)
    ravi = str(uid("employee", "ravi"))
    other_outlet = str(uid("outlet", "koramangala"))
    published = version(
        "indiranagar:2026-10-19:v3",
        WEEK,
        build_roster(WEEK, with_preferred_extras=True),
        version_number=3,
        status="published",
        source="manual",
        reason="Manager manual edit",
        base_version_id=uid("version", "indiranagar:2026-10-19:v2"),
        optimization_run_id=None,
        created_by_user_id=uid("user", "manager_indiranagar"),
        approved_by_user_id=uid("user", "manager_indiranagar"),
        created_at=stamp("2026-10-17T15:12:00"),
        published_at=stamp("2026-10-17T15:14:00"),
    )
    balanced_roster = build_roster(NEXT_WEEK, with_preferred_extras=True)
    lean_roster = build_roster(NEXT_WEEK, with_preferred_extras=False)
    run_id = uid("run", f"generate:{NEXT_WEEK}")

    def draft(key: str, number: int, roster: list[PlannedShift], strategy: str) -> s.ScheduleVersion:
        return version(
            f"indiranagar:{NEXT_WEEK}:{key}",
            NEXT_WEEK,
            roster,
            version_number=number,
            status="draft",
            source="generate",
            reason=f"Generated ({strategy})",
            base_version_id=None,
            optimization_run_id=run_id,
            created_by_user_id=None,
            approved_by_user_id=None,
            created_at=stamp("2026-10-18T19:40:02"),
            published_at=None,
        )

    d1 = draft("draft1", 1, balanced_roster, "balanced")
    d2 = draft("draft2", 2, lean_roster, "lowest_cost")

    def candidate(
        rank: int,
        v: s.ScheduleVersion,
        strategy: s.Strategy,
        status: Literal["OPTIMAL", "FEASIBLE"] = "OPTIMAL",
    ) -> s.Candidate:
        return s.Candidate(
            id=uid("candidate", f"{rank}:{status}"),
            rank=rank,
            strategy=strategy,
            solver_status=status,
            proven_optimal=status == "OPTIMAL",
            draft_version_id=v.id,
            metrics=v.metrics,
            changed_shifts=len(v.shifts),
            validation=v.validation,
        )

    done = dict(
        started_at=stamp("2026-10-18T19:40:00.400"),
        finished_at=stamp("2026-10-18T19:40:02.100"),
        solver_wall_ms=1640,
        poll_after_ms=None,
    )
    gen_path = "/v2/outlets/{outlet_id}/schedules/{week_start}/generate"
    gen_req = {
        "path_params": {"outlet_id": ind, "week_start": NEXT_WEEK.isoformat()},
        "headers": {"Idempotency-Key": "gen-7d1c2e9a"},
        "body": s.GenerateRequest().model_dump(mode="json"),
    }
    week_req = {"path_params": {"outlet_id": ind, "week_start": WEEK.isoformat()}}
    run_req = {"path_params": {"run_id": str(run_id)}}
    stale_emp = employee(EMP["ravi"]).model_copy(update={"revision": 2})
    week_etag = {"ETag": f'"week-{published.id}"'}
    immutable = {"Cache-Control": "private, max-age=31536000, immutable"}
    ravi_skill_ids = {sh.skill_id for sh in published.shifts if sh.employee_id == uid("employee", "ravi")}

    def other_outlet_week(key: str) -> s.ScheduleVersion:
        return version(
            f"{key}:{WEEK}:v1",
            WEEK,
            build_roster(WEEK, with_preferred_extras=True, staff=STAFF[key]),
            outlet_key=key,
            version_number=1,
            status="published",
            source="seed",
            reason="Initial roster",
            base_version_id=None,
            optimization_run_id=None,
            created_by_user_id=uid("user", "owner"),
            approved_by_user_id=uid("user", "owner"),
            created_at=stamp("2026-10-16T18:00:00"),
            published_at=stamp("2026-10-16T18:05:00"),
        )

    owner_weeks = {key: other_outlet_week(key) for key in ("koramangala", "hsr")}

    return [
        Fixture(
            "session.demo.manager",
            "createDemoSession",
            "POST",
            "/v2/session/demo",
            None,
            201,
            s.DemoSession(
                access_token="demo.synthetic.token.not-a-real-jwt",
                expires_at=stamp("2026-10-18T21:40:00"),
                me=me("manager_indiranagar"),
            ),
            {"body": {"persona": "manager"}},
        ),
        Fixture(
            "session.demo.disabled",
            "createDemoSession",
            "POST",
            "/v2/session/demo",
            None,
            403,
            error("permission_denied", "Demo sessions are not available on this deployment."),
            {"body": {"persona": "owner"}},
        ),
        Fixture("me.owner", "getMe", "GET", "/v2/me", "owner", 200, me("owner")),
        Fixture(
            "me.manager", "getMe", "GET", "/v2/me", "manager_indiranagar", 200, me("manager_indiranagar")
        ),
        Fixture("me.staff", "getMe", "GET", "/v2/me", "staff_ravi", 200, me("staff_ravi")),
        Fixture(
            "me.unauthenticated",
            "getMe",
            "GET",
            "/v2/me",
            None,
            401,
            error("unauthenticated", "Sign in to continue."),
        ),
        Fixture(
            "outlets.owner",
            "listOutlets",
            "GET",
            "/v2/outlets",
            "owner",
            200,
            s.OutletList(items=[outlet(k, n) for k, n in OUTLETS]),
        ),
        Fixture(
            "outlets.manager",
            "listOutlets",
            "GET",
            "/v2/outlets",
            "manager_indiranagar",
            200,
            s.OutletList(items=[outlet(*OUTLETS[0])]),
        ),
        Fixture(
            "skills.list",
            "listSkills",
            "GET",
            "/v2/skills",
            "manager_indiranagar",
            200,
            s.SkillList(items=[s.Skill(id=SKILL[n], name=n) for n in SKILLS]),
        ),
        Fixture(
            "employees.list",
            "listEmployees",
            "GET",
            "/v2/employees",
            "manager_indiranagar",
            200,
            s.EmployeeList(items=[employee(e) for e in EMPLOYEES], next_cursor=None),
            {"query": {"outlet_id": ind, "status": "active"}},
        ),
        Fixture(
            "employees.list.other_outlet_denied",
            "listEmployees",
            "GET",
            "/v2/employees",
            "manager_indiranagar",
            403,
            error("permission_denied", "You can only access your own outlet."),
            {"query": {"outlet_id": other_outlet}},
        ),
        Fixture(
            "employees.get",
            "getEmployee",
            "GET",
            "/v2/employees/{employee_id}",
            "manager_indiranagar",
            200,
            employee(EMP["ravi"]),
            {"path_params": {"employee_id": ravi}},
        ),
        Fixture(
            "employees.get.not_found",
            "getEmployee",
            "GET",
            "/v2/employees/{employee_id}",
            "manager_indiranagar",
            404,
            error("not_found", "Employee not found."),
            {"path_params": {"employee_id": str(uid("employee", "missing"))}},
        ),
        Fixture(
            "employees.create",
            "createEmployee",
            "POST",
            "/v2/employees",
            "manager_indiranagar",
            201,
            employee(Emp("tara", "Tara Singh", ("Barista", "Cashier"), 159)),
            {
                "headers": {"Idempotency-Key": "emp-3f9a1b77"},
                "body": s.EmployeeCreate(
                    **employee(Emp("tara", "Tara Singh", ("Barista", "Cashier"), 159)).model_dump(
                        exclude={"id", "revision"}
                    )
                ).model_dump(mode="json"),
            },
        ),
        Fixture(
            "employees.create.invalid",
            "createEmployee",
            "POST",
            "/v2/employees",
            "manager_indiranagar",
            422,
            error(
                "validation_failed",
                "Some fields need attention.",
                fields=[
                    {"path": ["name"], "message": "Name is required."},
                    {"path": ["max_weekly_minutes"], "message": "Must be at least regular_weekly_minutes."},
                ],
            ),
            {"headers": {"Idempotency-Key": "emp-0c2d4e11"}},
        ),
        Fixture(
            "employees.update",
            "updateEmployee",
            "PATCH",
            "/v2/employees/{employee_id}",
            "manager_indiranagar",
            200,
            stale_emp,
            {"path_params": {"employee_id": ravi}, "body": {"base_revision": 1, "tags": []}},
        ),
        Fixture(
            "employees.update.stale",
            "updateEmployee",
            "PATCH",
            "/v2/employees/{employee_id}",
            "manager_indiranagar",
            409,
            error(
                "stale_version",
                "This employee was changed by someone else. Reload and try again.",
                current_revision=2,
            ),
            {"path_params": {"employee_id": ravi}, "body": {"base_revision": 1, "tags": ["senior"]}},
        ),
        Fixture(
            "availability.get",
            "getAvailability",
            "GET",
            "/v2/employees/{employee_id}/availability",
            "manager_indiranagar",
            200,
            availability(EMP["ravi"]),
            {"path_params": {"employee_id": ravi}},
        ),
        Fixture(
            "availability.get.student",
            "getAvailability",
            "GET",
            "/v2/employees/{employee_id}/availability",
            "manager_indiranagar",
            200,
            availability(EMP["rohit"]),
            {"path_params": {"employee_id": str(uid("employee", "rohit"))}},
        ),
        Fixture(
            "availability.put.invalid",
            "putAvailability",
            "PUT",
            "/v2/employees/{employee_id}/availability",
            "manager_indiranagar",
            422,
            error(
                "validation_failed",
                "Some fields need attention.",
                fields=[
                    {"path": ["windows", 0, "end_minute"], "message": "end_minute must be after start_minute"}
                ],
            ),
            {"path_params": {"employee_id": ravi}},
        ),
        Fixture(
            "availability.put",
            "putAvailability",
            "PUT",
            "/v2/employees/{employee_id}/availability",
            "manager_indiranagar",
            200,
            availability(EMP["ravi"]).model_copy(update={"revision": 2}),
            {
                "path_params": {"employee_id": ravi},
                "body": s.AvailabilityUpdate(
                    base_revision=1, windows=availability(EMP["ravi"]).windows
                ).model_dump(mode="json"),
            },
        ),
        Fixture(
            "staffing.put",
            "putStaffingRequirements",
            "PUT",
            "/v2/outlets/{outlet_id}/staffing-requirements",
            "manager_indiranagar",
            200,
            staffing(WEEK).model_copy(update={"demand_revision": 4}),
            {
                "path_params": {"outlet_id": ind},
                "query": {"week_start": WEEK.isoformat()},
                "body": s.StaffingRequirementsUpdate(
                    base_demand_revision=3, intervals=staffing(WEEK).intervals
                ).model_dump(mode="json"),
            },
        ),
        Fixture(
            "staffing.get",
            "getStaffingRequirements",
            "GET",
            "/v2/outlets/{outlet_id}/staffing-requirements",
            "manager_indiranagar",
            200,
            staffing(WEEK),
            {"path_params": {"outlet_id": ind}, "query": {"week_start": WEEK.isoformat()}},
        ),
        Fixture(
            "schedule_week.published",
            "getScheduleWeek",
            "GET",
            "/v2/outlets/{outlet_id}/schedules/{week_start}",
            "manager_indiranagar",
            200,
            s.ScheduleWeek(
                outlet_id=HOME,
                week_start=WEEK,
                timezone=TZ,
                schedule_id=uid("schedule", f"indiranagar:{WEEK}"),
                current_version=published,
                drafts=[],
                employees=roster_employees(published),
                absences=requested_leave(published, WEEK + timedelta(days=3)),
            ),
            week_req,
            week_etag,
        ),
        Fixture(
            "schedule_week.empty",
            "getScheduleWeek",
            "GET",
            "/v2/outlets/{outlet_id}/schedules/{week_start}",
            "manager_indiranagar",
            200,
            s.ScheduleWeek(
                outlet_id=HOME,
                week_start=NEXT_WEEK,
                timezone=TZ,
                schedule_id=None,
                current_version=None,
                drafts=[],
                employees=roster_employees(None),
                absences=[],
            ),
            {"path_params": {"outlet_id": ind, "week_start": NEXT_WEEK.isoformat()}},
        ),
        Fixture(
            "schedule_week.denied",
            "getScheduleWeek",
            "GET",
            "/v2/outlets/{outlet_id}/schedules/{week_start}",
            "manager_indiranagar",
            403,
            error("permission_denied", "You can only access your own outlet."),
            {"path_params": {"outlet_id": other_outlet, "week_start": WEEK.isoformat()}},
        ),
        Fixture(
            "my_week.staff",
            "getMyWeek",
            "GET",
            "/v2/me/shifts",
            "staff_ravi",
            200,
            s.MyWeek(
                employee_id=uid("employee", "ravi"),
                week_start=WEEK,
                shifts=[sh for sh in published.shifts if sh.employee_id == uid("employee", "ravi")],
                outlets=[s.OutletRef(id=HOME, name="Indiranagar", timezone=TZ)],
                skills=[s.Skill(id=SKILL[n], name=n) for n in SKILLS if SKILL[n] in ravi_skill_ids],
            ),
            {"query": {"week_start": WEEK.isoformat()}},
        ),
        Fixture(
            "generate.accepted",
            "generateSchedule",
            "POST",
            gen_path,
            "manager_indiranagar",
            202,
            run("queued"),
            gen_req,
        ),
        Fixture(
            "generate.idempotency_conflict",
            "generateSchedule",
            "POST",
            gen_path,
            "manager_indiranagar",
            409,
            error(
                "idempotency_conflict",
                "This request key was already used with different input.",
                run_id=str(run_id),
            ),
            gen_req,
        ),
        Fixture(
            "generate.stale_base",
            "generateSchedule",
            "POST",
            gen_path,
            "manager_indiranagar",
            409,
            error(
                "stale_version",
                "The schedule changed since you opened it. Reload and try again.",
                current_version_id=str(published.id),
            ),
            {
                **week_req,
                "headers": {"Idempotency-Key": "gen-5b0e8c31"},
                "body": s.GenerateRequest(
                    base_version_id=uid("version", "indiranagar:2026-10-19:v2")
                ).model_dump(mode="json"),
            },
        ),
        Fixture(
            "generate.rate_limited",
            "generateSchedule",
            "POST",
            gen_path,
            "manager_indiranagar",
            429,
            error(
                "rate_limited",
                "Too many optimizations are running. Try again shortly.",
                retryable=True,
                retry_after_ms=3000,
            ),
            gen_req,
            {"Retry-After": "3"},
        ),
        Fixture(
            "run.queued",
            "getOptimizationRun",
            "GET",
            "/v2/optimization-runs/{run_id}",
            "manager_indiranagar",
            200,
            run("queued"),
            run_req,
        ),
        Fixture(
            "run.running",
            "getOptimizationRun",
            "GET",
            "/v2/optimization-runs/{run_id}",
            "manager_indiranagar",
            200,
            run("running", started_at=stamp("2026-10-18T19:40:00.400")),
            run_req,
        ),
        Fixture(
            "run.succeeded",
            "getOptimizationRun",
            "GET",
            "/v2/optimization-runs/{run_id}",
            "manager_indiranagar",
            200,
            run(
                "succeeded",
                solver_status="OPTIMAL",
                candidates=[candidate(1, d1, "balanced"), candidate(2, d2, "lowest_cost")],
                **done,
            ),
            run_req,
        ),
        Fixture(
            "run.time_limited_feasible",
            "getOptimizationRun",
            "GET",
            "/v2/optimization-runs/{run_id}",
            "manager_indiranagar",
            200,
            run(
                "succeeded",
                solver_status="FEASIBLE",
                candidates=[candidate(1, d1, "balanced", "FEASIBLE")],
                **{**done, "solver_wall_ms": 10000},
            ),
            run_req,
        ),
        Fixture(
            "run.infeasible",
            "getOptimizationRun",
            "GET",
            "/v2/optimization-runs/{run_id}",
            "manager_indiranagar",
            200,
            run(
                "succeeded",
                solver_status="INFEASIBLE",
                infeasibility=s.Infeasibility(
                    summary="Friday 19:00-22:00 needs 5 grill cooks; only 3 qualified employees are "
                    "available.",
                    shortages=[
                        s.Shortage(
                            outlet_id=HOME,
                            skill_id=SKILL["Grill"],
                            interval_start=at(date(2026, 10, 30), 1140),
                            interval_end=at(date(2026, 10, 30), 1320),
                            minimum_required=5,
                            max_assignable=3,
                        )
                    ],
                ),
                **done,
            ),
            run_req,
        ),
        Fixture(
            "run.no_solution_in_time",
            "getOptimizationRun",
            "GET",
            "/v2/optimization-runs/{run_id}",
            "manager_indiranagar",
            200,
            run("succeeded", solver_status="UNKNOWN", **{**done, "solver_wall_ms": 10000}),
            run_req,
        ),
        Fixture(
            "run.failed",
            "getOptimizationRun",
            "GET",
            "/v2/optimization-runs/{run_id}",
            "manager_indiranagar",
            200,
            run(
                "failed",
                error=s.ErrorBody(
                    code="internal",
                    retryable=True,
                    message="The optimizer stopped unexpectedly. Try again.",
                    trace_id="trc_9f2c41d07ab3",
                ),
                **done,
            ),
            run_req,
        ),
        Fixture(
            "schedule_version.draft",
            "getScheduleVersion",
            "GET",
            "/v2/schedule-versions/{version_id}",
            "manager_indiranagar",
            200,
            d1,
            {"path_params": {"version_id": str(d1.id)}},
            {"ETag": f'"{d1.id}"', "Cache-Control": "private, no-cache"},
        ),
        Fixture(
            "schedule_version.draft.lowest_cost",
            "getScheduleVersion",
            "GET",
            "/v2/schedule-versions/{version_id}",
            "manager_indiranagar",
            200,
            d2,
            {"path_params": {"version_id": str(d2.id)}},
            {"ETag": f'"{d2.id}"', "Cache-Control": "private, no-cache"},
        ),
        Fixture(
            "schedule_version.published",
            "getScheduleVersion",
            "GET",
            "/v2/schedule-versions/{version_id}",
            "manager_indiranagar",
            200,
            published,
            {"path_params": {"version_id": str(published.id)}},
            {"ETag": f'"{published.id}"', **immutable},
        ),
        Fixture(
            "schedule_version.not_modified",
            "getScheduleVersion",
            "GET",
            "/v2/schedule-versions/{version_id}",
            "manager_indiranagar",
            304,
            None,
            {
                "path_params": {"version_id": str(published.id)},
                "headers": {"If-None-Match": f'"{published.id}"'},
            },
            {"ETag": f'"{published.id}"'},
        ),
        Fixture(
            "schedule_week.not_modified",
            "getScheduleWeek",
            "GET",
            "/v2/outlets/{outlet_id}/schedules/{week_start}",
            "manager_indiranagar",
            304,
            None,
            {**week_req, "headers": {"If-None-Match": week_etag["ETag"]}},
            week_etag,
        ),
        Fixture(
            "generate.run_in_progress",
            "generateSchedule",
            "POST",
            gen_path,
            "manager_indiranagar",
            409,
            error(
                "run_in_progress",
                "An optimization is already running for this week. Showing its progress.",
                retryable=False,
                run_id=str(run_id),
            ),
            {**gen_req, "headers": {"Idempotency-Key": "gen-a91f30c2"}},
        ),
        Fixture(
            "employees.update.null_field",
            "updateEmployee",
            "PATCH",
            "/v2/employees/{employee_id}",
            "manager_indiranagar",
            422,
            error(
                "validation_failed",
                "Some fields need attention.",
                fields=[
                    {"path": ["name"], "message": "null is not allowed; omit a field to leave it unchanged"}
                ],
            ),
            {"path_params": {"employee_id": ravi}, "body": {"base_revision": 1, "name": None}},
        ),
        *[
            Fixture(
                f"schedule_week.owner.{key}",
                "getScheduleWeek",
                "GET",
                "/v2/outlets/{outlet_id}/schedules/{week_start}",
                "owner",
                200,
                s.ScheduleWeek(
                    outlet_id=uid("outlet", key),
                    week_start=WEEK,
                    timezone=TZ,
                    schedule_id=uid("schedule", f"{key}:{WEEK}"),
                    current_version=v,
                    drafts=[],
                    employees=roster_employees(v, STAFF[key], uid("outlet", key)),
                    absences=[],
                ),
                {"path_params": {"outlet_id": str(uid("outlet", key)), "week_start": WEEK.isoformat()}},
                {"ETag": f'"week-{v.id}"'},
            )
            for key, v in owner_weeks.items()
        ],
        *[
            Fixture(
                f"employees.list.owner.{key}",
                "listEmployees",
                "GET",
                "/v2/employees",
                "owner",
                200,
                s.EmployeeList(items=[employee(e, uid("outlet", key)) for e in STAFF[key]], next_cursor=None),
                {"query": {"outlet_id": str(uid("outlet", key)), "status": "active"}},
            )
            for key in owner_weeks
        ],
    ]


# ---------------------------------------------------------------- build


def openapi() -> dict[str, Any]:
    app = FastAPI(title="ShiftPilot scheduling v2 API", version=s.CONTRACT_VERSION)
    app.include_router(router)
    return app.openapi()


def render(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=True) + "\n"


def outputs() -> dict[Path, str]:
    fx = fixtures()
    names = [f.name for f in fx]
    if len(set(names)) != len(names):
        raise RuntimeError("duplicate fixture names")
    files = {OUT / "openapi.json": render(openapi())}
    for f in fx:
        files[OUT / "fixtures" / f"{f.name}.json"] = render(f.to_json())
    files[OUT / "fixtures" / "index.json"] = render(
        {
            "contract_version": s.CONTRACT_VERSION,
            "fixtures": [
                {
                    "name": f.name,
                    "operation_id": f.operation_id,
                    "status": f.status,
                    "schema": f.schema,
                }
                for f in fx
            ],
        }
    )
    return files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = outputs()
    existing = set((OUT / "fixtures").glob("*.json")) | {OUT / "openapi.json"}
    stale = sorted(str(p.relative_to(ROOT)) for p in existing - set(files) if p.exists())
    changed = sorted(
        str(p.relative_to(ROOT))
        for p, text in files.items()
        if not p.exists() or p.read_text(encoding="utf-8") != text
    )
    if args.check:
        for rel in changed + stale:
            print(f"out of date: {rel}")
        return 1 if changed or stale else 0
    for p, text in files.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    for rel in stale:
        (ROOT / rel).unlink()
    print(
        f"wrote {len(files)} files to {OUT.relative_to(ROOT)} ({len(changed)} changed, {len(stale)} removed)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
