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
from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI
from pydantic import BaseModel

from api.v2 import schemas as s
from api.v2.proposals import STALE_PUBLISHED
from api.v2.rosters import version_etag
from api.v2.routes import router
from jobs import forecast_worker
from scheduling import availability as sched_availability
from scheduling import diff as sched_diff
from scheduling import edits as sched_edits
from scheduling import forecast as sched_forecast
from scheduling import metrics as sched_metrics
from scheduling import model
from scheduling import recommend as sched_recommend
from scheduling import scenario as sched_scenario
from scheduling import solver as sched_solver
from scheduling import trace as sched_trace
from scheduling import validator as sched_validator
from scheduling.model import Window
from seed import v2 as seed_v2
from seed import world_snapshot
from seed.world import (
    CLOSE,
    EMP,
    EMPLOYEES,
    HOME,
    INTERVAL,
    IST,
    NEXT_WEEK,
    NS,
    OPEN,
    ORG,
    OUTLETS,
    SKILL,
    SKILLS,
    STAFF,
    TEMPLATES,
    TZ,
    WEEK,
    Emp,
    PlannedShift,
    at,
    availability_windows,
    build_roster,
    paid_minutes,
    rate_paise_per_minute,
    requirement,
    stamp,
    uid,
)
from seed.world import STAFF as world_staff
from seed.world import staffing_template as world_staffing_template

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "contracts" / "v2"


def evaluate(
    week: date, roster: list[PlannedShift], staff: list[Emp] | None = None, outlet_key: str = "indiranagar"
) -> tuple[s.Metrics, list[s.CoverageCell], s.ValidationResult]:
    """Independent of scheduling.metrics, so the contract checks the provider rather than copying it.
    staff: the outlet's employees (hours-preference alignment covers those with a weekly preference)."""
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
        hours_preference_deviation_minutes=_deviation(roster, staff or EMPLOYEES),
        fairness_burden_deviation=_fairness(week, roster, staff or EMPLOYEES, outlet_key),
        fairness_components=_components(roster),
    )
    return metrics, cells, s.ValidationResult(hard_violations=0, soft_violations=len(soft), violations=soft)


def _fairness(week: date, roster: list[PlannedShift], staff: list[Emp], outlet_key: str) -> float | None:
    """Independent of scheduling.fairness: closing (ends 22:00 or later) 3, weekend 2, second shift on a
    day 2, over the outlet's staff and bench, with the published fixture week as history for later weeks."""
    from seed.v2 import bench

    people = [e.key for e in [*staff, *bench(outlet_key)]]
    history = build_roster(WEEK, with_preferred_extras=True, staff=staff) if week > WEEK else []
    load: dict[str, int] = {k: 0 for k in people}
    days: dict[tuple[str, date], int] = {}
    for sh in [*history, *roster]:
        if sh.employee is None or sh.employee not in load:
            continue
        load[sh.employee] += 3 * (sh.template.end >= 1320) + 2 * (sh.day.weekday() >= 5)
        days[sh.employee, sh.day] = days.get((sh.employee, sh.day), 0) + 1
    for (who, _), n in days.items():
        load[who] += 2 * (n - 1)
    per40 = [load[k] * 2400 / 2880 for k in people]  # every seeded employee has a 48 h regular week
    mean = sum(per40) / len(per40)
    return round(sum(abs(v - mean) for v in per40) / len(per40), 2)


def _components(roster: list[PlannedShift]) -> s.FairnessComponents:
    """Independent of scheduling.fairness: this week's points by component (policy 1)."""
    worked = [sh for sh in roster if sh.employee]
    per_day: dict[tuple[str, date], int] = {}
    per_week: dict[str, int] = {}
    for sh in worked:
        who = sh.employee or ""
        per_day[who, sh.day] = per_day.get((who, sh.day), 0) + 1
        per_week[who] = per_week.get(who, 0) + paid_minutes(sh.template)
    return s.FairnessComponents(
        policy_version=1,
        closing=3 * sum(sh.template.end >= 1320 for sh in worked),
        weekend=2 * sum(sh.day.weekday() >= 5 for sh in worked),
        split=2 * sum(n - 1 for n in per_day.values()),
        overtime=sum(max(0, (m - 2880) // 60) for m in per_week.values()),
    )


def _deviation(roster: list[PlannedShift], staff: list[Emp]) -> int | None:
    preferring = [e for e in staff if e.preferred]  # the seed stores 2250 weekly minutes for them
    if not preferring:
        return None
    return sum(
        abs(sum(paid_minutes(sh.template) for sh in roster if sh.employee == e.key) - 2250)
        for e in preferring
    )


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
    metrics, cells, validation = evaluate(week, roster, world_staff[outlet_key], outlet_key)
    summary.setdefault("revision", 1)
    summary.setdefault("recorded_metrics", metrics)
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
    windows = [
        s.AvailabilityWindow(weekday=d, start_minute=a, end_minute=b, kind=k)  # type: ignore[arg-type]
        for d, a, b, k in availability_windows(e)
    ]
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
                            source="template",
                        )
                    )
    return s.StaffingRequirements(
        outlet_id=HOME, week_start=week, interval_minutes=INTERVAL, demand_revision=3, intervals=items
    )


def staffing_templates() -> s.StaffingTemplateSet:
    blocks = [
        s.StaffingTemplateBlock(
            weekday=wd,
            start_minute=start,
            end_minute=end,
            skill_id=SKILL[skill],
            minimum_required=mn,
            preferred_required=pref,
        )
        for wd, start, end, skill, mn, pref in world_staffing_template()
    ]
    blocks.sort(key=lambda b: (b.weekday, str(b.skill_id), b.start_minute))
    return s.StaffingTemplateSet(outlet_id=HOME, revision=1, items=blocks)


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
    arjun = world_snapshot.build("indiranagar", NEXT_WEEK).employees[uid("employee", "arjun")]
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
        """The draft a manager gets by selecting candidate `number` (candidates are not versions)."""
        return version(
            f"indiranagar:{NEXT_WEEK}:{key}",
            NEXT_WEEK,
            roster,
            version_number=number,
            status="draft",
            source="generate",
            reason=f"Selected option {number} ({strategy.replace('_', ' ')})",
            base_version_id=None,
            optimization_run_id=run_id,
            created_by_user_id=uid("user", "manager_indiranagar"),
            approved_by_user_id=None,
            created_at=stamp("2026-10-18T19:40:02"),
            published_at=None,
        )

    d1 = draft("draft1", 1, balanced_roster, "balanced")
    d2 = draft("draft2", 2, lean_roster, "lowest_cost")
    next_snap = world_snapshot.build("indiranagar", NEXT_WEEK, with_bench=True)

    def traced(rank: int, v: s.ScheduleVersion, strategy: str) -> tuple[s.DecisionTrace, list[s.TraceChange]]:
        """Empty week: rank 1 has no comparison, other ranks compare with the requested plan."""
        roster = [_to_model(sh) for sh in v.shifts]
        reference = None if rank == 1 else [_to_model(sh) for sh in d1.shifts]
        doc, rows, _ = sched_trace.build(next_snap, strategy, [], roster, reference)
        return s.DecisionTrace.model_validate(doc), [s.TraceChange.model_validate(r) for r in rows]

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
            materialized_version_id=None,
            metrics=v.metrics,
            changed_shifts=len(v.shifts),
            validation=v.validation,
            trace=traced(rank, v, strategy)[0],
        )

    def candidate_detail(c: s.Candidate, v: s.ScheduleVersion) -> s.CandidateDetail:
        added = [
            s.CandidateShift.model_validate(sh.model_dump(exclude={"id", "lock_reason"})) for sh in v.shifts
        ]
        return s.CandidateDetail.model_validate(
            c.model_dump()
            | {
                "run_id": run_id,
                "base_version_id": None,
                "diff": {"added": added, "changed": [], "removed": []},
                "trace_changes": traced(c.rank, v, c.strategy)[1],
            }
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
    no_cache = {"Cache-Control": "private, no-cache"}

    def vtag(v: s.ScheduleVersion) -> str:
        return version_etag(v.id, v.status, v.revision)

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
    # A public demo session: a private 2-hour sandbox copy of the synthetic org (B6.2).
    demo_manager = s.DemoSession(
        access_token="demo.synthetic.token.not-a-real-jwt",
        expires_at=stamp("2026-10-18T21:40:00"),
        me=me("manager_indiranagar"),
        sandbox_id=uid("org", "sandbox:example"),
        sandbox_expires_at=stamp("2026-10-18T21:40:00"),
    )
    # Saturday dinner needs a second grill cook at minimum and a fourth preferred.
    template = staffing_templates()
    saturday_rush = template.model_copy(
        update={
            "revision": 2,
            "items": [
                b.model_copy(update={"minimum_required": 2, "preferred_required": 4})
                if (b.weekday, b.skill_id, b.start_minute) == (5, SKILL["Grill"], 1080)
                else b
                for b in template.items
            ],
        }
    )

    return (
        p3_fixtures(published)
        + p4_fixtures(published)
        + p8_fixtures()
        + p9_fixtures(published)
        + p10_fixtures(published)
        + proposal_fixtures(d1)
        + import_fixtures()
        + rule_fixtures()
        + [
            Fixture(
                "session.demo.manager",
                "createDemoSession",
                "POST",
                "/v2/session/demo",
                None,
                201,
                demo_manager,
                {"body": {"persona": "manager"}},
            ),
            Fixture(
                "session.demo.switch_persona",
                "createDemoSession",
                "POST",
                "/v2/session/demo",
                None,
                201,
                demo_manager.model_copy(update={"me": me("staff_ravi")}),
                {"body": {"persona": "staff", "sandbox_id": str(demo_manager.sandbox_id)}},
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
                        {
                            "path": ["max_weekly_minutes"],
                            "message": "Must be at least regular_weekly_minutes.",
                        },
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
                        {
                            "path": ["windows", 0, "end_minute"],
                            "message": "end_minute must be after start_minute",
                        }
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
                "staffing_templates.list",
                "listStaffingTemplates",
                "GET",
                "/v2/outlets/{outlet_id}/staffing-templates",
                "manager_indiranagar",
                200,
                staffing_templates(),
                {"path_params": {"outlet_id": ind}},
            ),
            Fixture(
                "staffing_templates.put",
                "putStaffingTemplates",
                "PUT",
                "/v2/outlets/{outlet_id}/staffing-templates",
                "manager_indiranagar",
                200,
                saturday_rush,
                {
                    "path_params": {"outlet_id": ind},
                    "body": {
                        "base_revision": 1,
                        "items": [b.model_dump(mode="json") for b in saturday_rush.items],
                    },
                },
            ),
            Fixture(
                "staffing.expand",
                "expandStaffingRequirements",
                "POST",
                "/v2/outlets/{outlet_id}/staffing-requirements/expand",
                "manager_indiranagar",
                200,
                staffing(WEEK).model_copy(update={"demand_revision": 4}),
                {
                    "path_params": {"outlet_id": ind},
                    "query": {"week_start": WEEK.isoformat()},
                    "headers": {"Idempotency-Key": "expand-5c2e91a0"},
                    "body": {"base_demand_revision": 3, "use_demand_bands": False},
                },
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
                    portfolio=s.PortfolioSummary(
                        policy_version=1,
                        considered=["balanced", "lowest_cost", "fairness", "max_coverage"],
                        dropped=[
                            s.PortfolioDrop(strategy="fairness", reason="duplicate", detail=["balanced"]),
                            s.PortfolioDrop(strategy="max_coverage", reason="guardrail", detail=["cost"]),
                        ],
                    ),
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
                "run.candidates_expired",
                "getOptimizationRun",
                "GET",
                "/v2/optimization-runs/{run_id}",
                "manager_indiranagar",
                200,
                run("succeeded", solver_status="OPTIMAL", candidates=[], candidates_expired=True, **done),
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
                        conflict_set=[
                            s.ConflictItem(
                                kind="minimum_coverage",
                                message="Minimum Grill staffing on Friday 30 Oct",
                                relaxation=sched_solver.RELAX["minimum_coverage"],
                                skill_id=SKILL["Grill"],
                                day=date(2026, 10, 30),
                            ),
                            s.ConflictItem(
                                kind="no_overtime",
                                message="Arjun Rao cannot work beyond "
                                + sched_solver._hours(arjun.regular_weekly_minutes)
                                + " (no overtime)",
                                relaxation=sched_solver.RELAX["no_overtime"],
                                employee_id=arjun.id,
                                minutes=arjun.regular_weekly_minutes,
                            ),
                        ],
                        options=[
                            s.RelaxationOption(
                                kind="overtime",
                                summary="Allow Arjun Rao 2 h overtime",
                                employees=[
                                    s.RelaxationEmployee(
                                        employee_id=uid("employee", "arjun"),
                                        name="Arjun Rao",
                                        home_outlet_id=HOME,
                                        minutes=120,
                                    )
                                ],
                            ),
                            s.RelaxationOption(
                                kind="cross_outlet",
                                summary="Borrow Suresh Pillai from Koramangala for 7 h 30 min",
                                employees=[
                                    s.RelaxationEmployee(
                                        employee_id=uid("employee", "suresh"),
                                        name="Suresh Pillai",
                                        home_outlet_id=uid("outlet", "koramangala"),
                                        minutes=450,
                                    )
                                ],
                            ),
                            s.RelaxationOption(
                                kind="reduced_minimum",
                                summary="Operate Indiranagar Friday 19:00-22:00 with 3 Grill instead of 5",
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
                "candidate.detail",
                "getOptimizationCandidate",
                "GET",
                "/v2/optimization-candidates/{candidate_id}",
                "manager_indiranagar",
                200,
                candidate_detail(candidate(1, d1, "balanced"), d1),
                {"path_params": {"candidate_id": str(candidate(1, d1, "balanced").id)}},
            ),
            Fixture(
                "candidate.select",
                "selectOptimizationCandidate",
                "POST",
                "/v2/optimization-candidates/{candidate_id}/select",
                "manager_indiranagar",
                201,
                d1,
                {
                    "path_params": {"candidate_id": str(candidate(1, d1, "balanced").id)},
                    "headers": {"Idempotency-Key": "select-3b8e51d2"},
                },
            ),
            Fixture(
                "candidate.detail.lowest_cost",
                "getOptimizationCandidate",
                "GET",
                "/v2/optimization-candidates/{candidate_id}",
                "manager_indiranagar",
                200,
                candidate_detail(candidate(2, d2, "lowest_cost"), d2),
                {"path_params": {"candidate_id": str(candidate(2, d2, "lowest_cost").id)}},
            ),
            Fixture(
                "candidate.select.lowest_cost",
                "selectOptimizationCandidate",
                "POST",
                "/v2/optimization-candidates/{candidate_id}/select",
                "manager_indiranagar",
                201,
                d2,
                {
                    "path_params": {"candidate_id": str(candidate(2, d2, "lowest_cost").id)},
                    "headers": {"Idempotency-Key": "select-8d0c3f47"},
                },
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
                {"ETag": vtag(d1), **no_cache},
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
                {"ETag": vtag(d2), **no_cache},
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
                {"ETag": vtag(published), **no_cache},
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
                    "headers": {"If-None-Match": vtag(published)},
                },
                {"ETag": vtag(published)},
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
                        {
                            "path": ["name"],
                            "message": "null is not allowed; omit a field to leave it unchanged",
                        }
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
                    s.EmployeeList(
                        items=[employee(e, uid("outlet", key)) for e in STAFF[key]], next_cursor=None
                    ),
                    {"query": {"outlet_id": str(uid("outlet", key)), "status": "active"}},
                )
                for key in owner_weeks
            ],
        ]
    )


# ---------------------------------------------------------------- P3 (contract 2.3): drafts, edits, publish


def _to_model(sh: s.Shift) -> model.Shift:
    return model.Shift(
        sh.logical_shift_id,
        sh.outlet_id,
        sh.employee_id,
        sh.skill_id,
        sh.start_at,
        sh.end_at,
        sh.break_minutes,
        sh.break_start_at,
        sh.locked,
    )


def _to_contract(sh: model.Shift, version_key: str) -> s.Shift:
    return s.Shift(
        id=uid("version_shift", f"{version_key}:{sh.logical_id}"),
        logical_shift_id=sh.logical_id,
        outlet_id=sh.outlet_id,
        employee_id=sh.employee_id,
        skill_id=sh.skill_id,
        start_at=sh.start_at.astimezone(IST),
        end_at=sh.end_at.astimezone(IST),
        break_start_at=sh.break_start_at.astimezone(IST) if sh.break_start_at else None,
        break_minutes=sh.break_minutes,
        locked=sh.locked,
        lock_reason="Locked by manager" if sh.locked else None,
    )


def _evaluated(roster: list[model.Shift]) -> dict[str, Any]:
    snap = world_snapshot.build("indiranagar", WEEK, with_bench=True)
    m = sched_metrics.compute(snap, roster)
    return {
        "metrics": s.Metrics.model_validate(sched_metrics.as_contract(m)),
        "coverage": [
            s.CoverageCell(
                skill_id=c.skill_id,
                interval_start=c.interval_start.astimezone(IST),
                minimum_required=c.minimum_required,
                preferred_required=c.preferred_required,
                scheduled=c.scheduled,
            )
            for c in m.cells
        ],
        "validation": s.ValidationResult.model_validate(
            sched_validator.as_contract(sched_validator.validate(snap, roster))
        ),
    }


def _changes(
    before: list[model.Shift], after: list[model.Shift], key_before: str, key_after: str
) -> list[s.ShiftChange]:
    return [
        s.ShiftChange(
            logical_shift_id=c.logical_id,
            kinds=list(c.kinds),  # type: ignore[arg-type]
            before=_to_contract(c.before, key_before) if c.before else None,
            after=_to_contract(c.after, key_after) if c.after else None,
        )
        for c in sched_diff.diff(before, after)
    ]


def _summary(v: s.ScheduleVersion, **changes: Any) -> s.ScheduleVersionSummary:
    data = {k: getattr(v, k) for k in s.ScheduleVersionSummary.model_fields}
    return s.ScheduleVersionSummary(**{**data, **changes})


def p3_fixtures(published: s.ScheduleVersion) -> list[Fixture]:
    ind = str(HOME)
    manager = uid("user", "manager_indiranagar")
    base = [_to_model(sh) for sh in published.shifts]

    def draft(key: str, number: int, roster: list[model.Shift], **summary: Any) -> s.ScheduleVersion:
        evaluated = _evaluated(roster)
        return s.ScheduleVersion(
            id=uid("version", key),
            schedule_id=published.schedule_id,
            version_number=number,
            status="draft",
            optimization_run_id=None,
            approved_by_user_id=None,
            published_at=None,
            input_hash="sha256:" + uuid.uuid5(NS, f"input:{key}").hex,
            shifts=[_to_contract(sh, key) for sh in roster],
            **evaluated,
            recorded_metrics=evaluated["metrics"],
            **summary,
        )

    v4_key = f"indiranagar:{WEEK}:v4"
    draft_common = dict(
        source="manual",
        reason="Manager edit",
        base_version_id=published.id,
        created_by_user_id=manager,
        created_at=stamp("2026-10-18T19:05:00"),
    )
    v4 = draft(v4_key, 4, base, revision=1, **draft_common)

    # Preview: reassign a Tuesday Grill shift to Ravi, who is unavailable on Tuesdays.
    tuesday = WEEK + timedelta(days=1)
    target = next(
        sh for sh in base if sh.skill_id == SKILL["Grill"] and sh.start_at.astimezone(IST).date() == tuesday
    )
    reassign = sched_edits.Edit("update", target.logical_id, {"employee_id": uid("employee", "ravi")})
    previewed = sched_edits.apply(base, [reassign], HOME)
    preview = s.EditPreview(
        version_id=v4.id,
        expected_revision=1,
        shifts=[_to_contract(sh, v4_key) for sh in previewed],
        changes=_changes(base, previewed, v4_key, v4_key),
        **{k: v for k, v in _evaluated(previewed).items() if k != "coverage"},
    )
    preview_request = {
        "expected_revision": 1,
        "edits": [
            {
                "op": "update",
                "logical_shift_id": str(target.logical_id),
                "employee_id": str(uid("employee", "ravi")),
            }
        ],
    }

    # Apply: lock Monday's opening Grill shift (valid), which moves the draft to revision 2.
    monday_open = next(
        sh
        for sh in base
        if sh.skill_id == SKILL["Grill"] and not sh.locked and sh.start_at.astimezone(IST).date() == WEEK
    )
    applied_roster = sched_edits.apply(base, [sched_edits.Edit("lock", monday_open.logical_id)], HOME)
    v4_applied = draft(v4_key, 4, applied_roster, revision=2, **draft_common)
    apply_request = {
        "expected_revision": 1,
        "edits": [
            {
                "op": "lock",
                "logical_shift_id": str(monday_open.logical_id),
                "reason": "Opening cook confirmed",
            }
        ],
    }
    version_path = "/v2/schedule-versions/{version_id}"
    v4_req = {"path_params": {"version_id": str(v4.id)}}

    # History: v2 (superseded), v3 (published), v4 (draft). Restore v2 as a new draft v5.
    v2_key = f"indiranagar:{WEEK}:v2"
    v2_roster = [_to_model(sh) for sh in to_shifts(v2_key, build_roster(WEEK, with_preferred_extras=False))]
    v2_summary = s.ScheduleVersionSummary(
        id=uid("version", v2_key),
        schedule_id=published.schedule_id,
        version_number=2,
        status="superseded",
        source="generate",
        reason="Generated (lowest cost)",
        base_version_id=None,
        optimization_run_id=None,
        created_by_user_id=None,
        approved_by_user_id=manager,
        created_at=stamp("2026-10-16T18:00:00"),
        published_at=stamp("2026-10-16T18:10:00"),
        revision=1,
        recorded_metrics=_evaluated(v2_roster)["metrics"],
    )
    v5_key = f"indiranagar:{WEEK}:v5"
    v5 = draft(
        v5_key,
        5,
        v2_roster,
        revision=1,
        source="restore",
        reason="Restored from version 2",
        base_version_id=published.id,
        created_by_user_id=manager,
        created_at=stamp("2026-10-18T19:20:00"),
    )
    published_v4 = _summary(
        v4_applied, status="published", approved_by_user_id=manager, published_at=stamp("2026-10-18T19:12:00")
    )
    hard = [v for v in preview.validation.violations if v.severity == "hard"]

    return [
        Fixture(
            "shift_templates.list",
            "listShiftTemplates",
            "GET",
            "/v2/outlets/{outlet_id}/shift-templates",
            "manager_indiranagar",
            200,
            s.ShiftTemplateList(
                outlet_id=HOME,
                items=sorted(
                    (
                        s.ShiftTemplate(
                            id=uid("template", f"indiranagar:{t.key}"),
                            name=t.key.title(),
                            skill_id=None,
                            start_minute=t.start,
                            duration_minutes=t.end - t.start,
                            break_minutes=30 if t.break_start is not None else 0,
                            break_start_minute=t.break_start - t.start if t.break_start is not None else None,
                        )
                        for t in TEMPLATES.values()
                    ),
                    key=lambda x: (x.start_minute, x.duration_minutes, x.name),
                ),
            ),
            {"path_params": {"outlet_id": ind}},
        ),
        Fixture(
            "draft.create",
            "createDraft",
            "POST",
            "/v2/outlets/{outlet_id}/schedules/{week_start}/drafts",
            "manager_indiranagar",
            201,
            v4,
            {
                "path_params": {"outlet_id": ind, "week_start": WEEK.isoformat()},
                "headers": {"Idempotency-Key": "draft-51c0e7aa"},
                "body": {"base_version_id": str(published.id), "copy_from_version_id": None},
            },
        ),
        Fixture(
            "edits.preview",
            "previewEdits",
            "POST",
            version_path + "/edits/preview",
            "manager_indiranagar",
            200,
            preview,
            {**v4_req, "body": preview_request},
        ),
        Fixture(
            "edits.apply",
            "applyEdits",
            "POST",
            version_path + "/edits",
            "manager_indiranagar",
            200,
            v4_applied,
            {**v4_req, "body": apply_request},
        ),
        Fixture(
            "edits.apply.stale",
            "applyEdits",
            "POST",
            version_path + "/edits",
            "manager_indiranagar",
            409,
            error(
                "stale_version",
                "This draft was changed by someone else. Reload and try again.",
                current_revision=2,
            ),
            {**v4_req, "body": apply_request},
        ),
        Fixture(
            "edits.apply.not_draft",
            "applyEdits",
            "POST",
            version_path + "/edits",
            "manager_indiranagar",
            409,
            error("conflict", "Published versions cannot be edited. Create a draft first."),
            {"path_params": {"version_id": str(published.id)}, "body": apply_request},
        ),
        Fixture(
            "publish",
            "publishVersion",
            "POST",
            version_path + "/publish",
            "manager_indiranagar",
            200,
            s.PublishResult(
                schedule_id=published.schedule_id, published=published_v4, superseded_version_id=published.id
            ),
            {
                **v4_req,
                "headers": {"Idempotency-Key": "pub-7f3a9b12"},
                "body": {"expected_base_version_id": str(published.id), "expected_revision": 2},
            },
        ),
        Fixture(
            "publish.blocked",
            "publishVersion",
            "POST",
            version_path + "/publish",
            "manager_indiranagar",
            422,
            error(
                "validation_failed",
                "This draft breaks scheduling rules. Fix them before publishing.",
                violations=[v.model_dump(mode="json") for v in hard],
            ),
            {
                **v4_req,
                "headers": {"Idempotency-Key": "pub-0d44e9c1"},
                "body": {"expected_base_version_id": str(published.id), "expected_revision": 3},
            },
        ),
        Fixture(
            "publish.stale_base",
            "publishVersion",
            "POST",
            version_path + "/publish",
            "manager_indiranagar",
            409,
            error(
                "stale_version",
                "Someone published a newer version. Review the changes and try again.",
                current_version_id=str(uid("version", f"indiranagar:{WEEK}:v6")),
            ),
            {
                **v4_req,
                "headers": {"Idempotency-Key": "pub-91be22f0"},
                "body": {"expected_base_version_id": str(published.id), "expected_revision": 2},
            },
        ),
        Fixture(
            "draft.discard",
            "discardDraft",
            "POST",
            version_path + "/discard",
            "manager_indiranagar",
            200,
            _summary(v4_applied, status="discarded"),
            v4_req,
        ),
        Fixture(
            "versions.list",
            "listVersions",
            "GET",
            "/v2/schedules/{schedule_id}/versions",
            "manager_indiranagar",
            200,
            s.VersionHistory(
                schedule_id=published.schedule_id,
                current_version_id=published.id,
                items=[_summary(v5), _summary(v4_applied), _summary(published), v2_summary],
            ),
            {"path_params": {"schedule_id": str(published.schedule_id)}},
        ),
        Fixture(
            "versions.compare",
            "compareVersions",
            "GET",
            version_path + "/compare",
            "manager_indiranagar",
            200,
            s.VersionDiff(
                from_version_id=published.id,
                to_version_id=v4_applied.id,
                changes=_changes(base, applied_roster, f"indiranagar:{WEEK}:v3", v4_key),
                metrics_from=published.metrics,
                metrics_to=v4_applied.metrics,
            ),
            {**v4_req, "query": {"with": str(published.id)}},
        ),
        Fixture(
            "versions.restore",
            "restoreVersion",
            "POST",
            version_path + "/restore",
            "manager_indiranagar",
            201,
            v5,
            {
                "path_params": {"version_id": str(v2_summary.id)},
                "headers": {"Idempotency-Key": "restore-3e8d"},
                "body": {"expected_base_version_id": str(published.id)},
            },
        ),
    ]


# ---------------------------------------------------------------- P4 (contract 2.4): absences and repair


def p8_fixtures() -> list[Fixture]:
    """Forecast next week from the seeded order history exactly as the worker would (compute is pure)."""
    rows = seed_v2.org_rows(seed_v2.SPICE).tables
    home_rows = [r for r in rows["demand_inputs"] if r["outlet_id"] == HOME]
    templates = [r for r in rows["staffing_templates"] if r["outlet_id"] == HOME]
    doc: dict[str, Any] = {
        "tz": "Asia/Kolkata",
        "week_start": NEXT_WEEK.isoformat(),
        "history": sorted([r["interval_start"].isoformat(), r["orders"]] for r in home_rows),
        "blocks": [
            [
                t["weekday"],
                t["start_minute"],
                t["end_minute"],
                str(t["skill_id"]),
                t["minimum_required"],
                t["preferred_required"],
            ]
            for t in templates
        ],
        "bands": [
            [str(b["skill_id"]), b["min_orders"], b["max_orders"], b["staff_minimum"], b["staff_preferred"]]
            for b in rows["demand_bands"]
        ],
        "manual": [],
        "base_demand_revision": 1,
    }
    result = forecast_worker.compute(doc)
    run_id = uid("forecast_run", f"indiranagar:{NEXT_WEEK}")
    proposal_id = uid("staffing_proposal", f"indiranagar:{NEXT_WEEK}")
    common: dict[str, Any] = dict(
        id=run_id,
        outlet_id=HOME,
        week_start=NEXT_WEEK,
        model_version=sched_forecast.MODEL_VERSION,
        queued_at=stamp("2026-10-23T09:00:00"),
    )
    queued = s.ForecastRun(
        job_state="queued",
        quality=None,
        metrics=None,
        points=[],
        proposal_id=None,
        error=None,
        finished_at=None,
        poll_after_ms=1000,
        **common,
    )
    done = s.ForecastRun(
        job_state="succeeded",
        quality="passed" if result["metrics"]["passed"] else "failed",
        metrics=s.ForecastMetrics.model_validate(result["metrics"]),
        points=[
            s.ForecastPoint(
                interval_start=pt.interval_start,
                predicted=pt.predicted,
                lower=pt.lower,
                upper=pt.upper,
                samples=pt.samples,
            )
            for pt in result["points"]
        ],
        proposal_id=proposal_id if result["rows"] is not None else None,
        error=None,
        finished_at=stamp("2026-10-23T09:00:01.200"),
        poll_after_ms=None,
        **common,
    )
    early = NEXT_WEEK - timedelta(weeks=6)
    failed = s.ForecastRun(
        job_state="failed",
        quality=None,
        metrics=None,
        points=[],
        proposal_id=None,
        error=s.ErrorBody(
            code="validation_failed",
            message=f"Needs at least {sched_forecast.MIN_WEEKS + 1} weeks of order history before this week "
            "to forecast and test it.",
            retryable=False,
            details={"reason": "NOT_ENOUGH_HISTORY"},
        ),
        finished_at=stamp("2026-10-23T09:05:00.300"),
        poll_after_ms=None,
        **{**common, "id": uid("forecast_run", f"indiranagar:{early}"), "week_start": early},
    )
    proposed = [s.ProposedRequirement.model_validate(r) for r in result["rows"] or []]
    forecast_rows = [r for r in proposed if r.source == "forecast"]
    proposal = s.StaffingProposal(
        id=proposal_id,
        outlet_id=HOME,
        week_start=NEXT_WEEK,
        forecast_run_id=run_id,
        status="pending",
        base_demand_revision=1,
        created_at=stamp("2026-10-23T09:00:01.200"),
        decided_by_user_id=None,
        decided_at=None,
        changes=s.ProposalChanges(
            added=0,
            changed=len(forecast_rows),
            removed=0,
            unchanged=len(proposed) - len(forecast_rows),
            manual_kept=0,
        ),
        rows=proposed,
    )
    accepted = s.StaffingRequirements(
        outlet_id=HOME,
        week_start=NEXT_WEEK,
        interval_minutes=30,
        demand_revision=2,
        intervals=[
            s.StaffingInterval(
                skill_id=r.skill_id,
                interval_start=r.interval_start,
                interval_end=r.interval_end,
                minimum_required=r.minimum,
                preferred_required=r.preferred,
                source=r.source,
            )
            for r in proposed
        ],
    )
    manager = "manager_indiranagar"
    path = {"path_params": {"proposal_id": str(proposal_id)}}
    return [
        Fixture(
            "forecast.request",
            "requestForecast",
            "POST",
            "/v2/outlets/{outlet_id}/forecast-runs",
            manager,
            202,
            queued,
            {
                "path_params": {"outlet_id": str(HOME)},
                "headers": {"Idempotency-Key": "forecast-2b7c"},
                "body": {"week_start": NEXT_WEEK.isoformat()},
            },
        ),
        Fixture(
            "forecast.run.succeeded",
            "getForecastRun",
            "GET",
            "/v2/forecast-runs/{run_id}",
            manager,
            200,
            done,
            {"path_params": {"run_id": str(run_id)}},
        ),
        Fixture(
            "forecast.run.not_enough_history",
            "getForecastRun",
            "GET",
            "/v2/forecast-runs/{run_id}",
            manager,
            200,
            failed,
            {"path_params": {"run_id": str(failed.id)}},
        ),
        Fixture(
            "staffing_proposal.get",
            "getStaffingProposal",
            "GET",
            "/v2/staffing-requirement-proposals/{proposal_id}",
            manager,
            200,
            proposal,
            path,
        ),
        Fixture(
            "staffing_proposal.accept",
            "acceptStaffingProposal",
            "POST",
            "/v2/staffing-requirement-proposals/{proposal_id}/accept",
            manager,
            200,
            accepted,
            {**path, "headers": {"Idempotency-Key": "accept-staffing-5d1e"}},
        ),
        Fixture(
            "staffing_proposal.accept.stale",
            "acceptStaffingProposal",
            "POST",
            "/v2/staffing-requirement-proposals/{proposal_id}/accept",
            manager,
            409,
            error(
                "stale_version",
                "Staffing needs changed after this forecast. Run the forecast again.",
                current_demand_revision=2,
            ),
            {**path, "headers": {"Idempotency-Key": "accept-staffing-9f02"}},
        ),
        Fixture(
            "staffing_proposal.reject",
            "rejectStaffingProposal",
            "POST",
            "/v2/staffing-requirement-proposals/{proposal_id}/reject",
            manager,
            200,
            proposal.model_copy(
                update={
                    "status": "rejected",
                    "decided_by_user_id": uid("user", "manager_indiranagar"),
                    "decided_at": stamp("2026-10-23T09:10:00"),
                }
            ),
            path,
        ),
    ]


def p9_fixtures(published: s.ScheduleVersion) -> list[Fixture]:
    """Shift requests on the published week: a claim, a swap and their manager outcomes."""
    ravi, arjun = uid("employee", "ravi"), uid("employee", "arjun")
    mine = next(sh for sh in published.shifts if sh.employee_id == ravi and not sh.locked)
    theirs = next(
        sh
        for sh in published.shifts
        if sh.employee_id == arjun and sh.start_at.date() != mine.start_at.date()
    )
    template = next(sh for sh in published.shifts if sh.skill_id == SKILL["Grill"] and sh.employee_id != ravi)
    open_shift = template.model_copy(
        update={
            "id": uid("version_shift", "open:grill"),
            "logical_shift_id": uid("logical_shift", "open:grill"),
            "employee_id": None,
        }
    )
    checks = [
        s.ExplanationFact(
            code="skill", ok=True, message="Qualified for Grill", facts={"skill_id": str(SKILL["Grill"])}
        ),
        s.ExplanationFact(code="available", ok=True, message="Available for the shift"),
        s.ExplanationFact(code="no_conflict", ok=True, message="No overlapping shift and rest rules met"),
        s.ExplanationFact(
            code="weekly_hours",
            ok=True,
            message="38h this week after the change",
            facts={"weekly_minutes": 2280, "regular_weekly_minutes": 2880},
        ),
        s.ExplanationFact(code="rules", ok=True, message="Within their scheduling rules"),
        s.ExplanationFact(
            code="travel", ok=True, message="Works at this outlet", facts={"travel_minutes": 0}
        ),
    ]

    def request(n: str, kind: str, status: str, shift: s.Shift, **kw: Any) -> s.ShiftRequestView:
        base: dict[str, Any] = dict(
            id=uid("shift_request", n),
            type=kind,
            status=status,
            schedule_id=published.schedule_id,
            outlet_id=HOME,
            week_start=WEEK,
            base_version_id=published.id,
            shift=shift,
            target_shift=None,
            requester_employee_id=ravi,
            target_employee_id=None,
            note=None,
            created_at=stamp("2026-10-18T10:00:00"),
            expires_at=shift.start_at,
            decided_by_user_id=None,
            decided_at=None,
            published_version_id=None,
        )
        return s.ShiftRequestView(**{**base, **kw})

    claim = request("claim", "open_shift_claim", "pending_manager", open_shift)
    swap_open = request(
        "swap",
        "swap",
        "open",
        mine,
        target_shift=theirs,
        target_employee_id=arjun,
        note="Exam on Thursday",
        expires_at=min(mine.start_at, theirs.start_at),
    )
    swap_pending = swap_open.model_copy(update={"status": "pending_manager"})
    decided = {
        "decided_by_user_id": uid("user", "manager_indiranagar"),
        "decided_at": stamp("2026-10-18T11:00:00"),
    }
    approved = claim.model_copy(
        update={
            "status": "approved",
            "published_version_id": uid("version", "indiranagar:request:claim"),
            **decided,
        }
    )
    rest = s.Violation(
        code="insufficient_rest",
        severity="hard",
        message="Ravi Kumar would have 8h rest between shifts; 10h required.",
        employee_id=ravi,
        logical_shift_ids=[mine.logical_shift_id, theirs.logical_shift_id],
        facts={"rest_minutes": 480, "required_rest_minutes": 600},
    )
    manager, staff = "manager_indiranagar", "staff_ravi"
    by_id = {"path_params": {"request_id": str(claim.id)}}
    swap_path = {"path_params": {"request_id": str(swap_open.id)}}
    return [
        Fixture(
            "me.open_shifts",
            "getMyOpenShifts",
            "GET",
            "/v2/me/open-shifts",
            staff,
            200,
            s.OpenShiftList(
                week_start=WEEK,
                items=[s.OpenShift(version_id=published.id, shift=open_shift, reasons=checks)],
            ),
            {"query": {"week_start": WEEK.isoformat()}},
        ),
        Fixture(
            "shift_request.create.claim",
            "createShiftRequest",
            "POST",
            "/v2/me/shift-requests",
            staff,
            201,
            claim,
            {"body": {"type": "open_shift_claim", "logical_shift_id": str(open_shift.logical_shift_id)}},
        ),
        Fixture(
            "shift_request.create.swap",
            "createShiftRequest",
            "POST",
            "/v2/me/shift-requests",
            staff,
            201,
            swap_open,
            {
                "body": {
                    "type": "swap",
                    "logical_shift_id": str(mine.logical_shift_id),
                    "target_logical_shift_id": str(theirs.logical_shift_id),
                    "note": "Exam on Thursday",
                }
            },
        ),
        Fixture(
            "shift_request.create.invalid",
            "createShiftRequest",
            "POST",
            "/v2/me/shift-requests",
            staff,
            422,
            error(
                "validation_failed",
                f"This swap breaks a rule: {rest.message}",
                violations=[rest.model_dump(mode="json")],
            ),
            {
                "body": {
                    "type": "swap",
                    "logical_shift_id": str(mine.logical_shift_id),
                    "target_logical_shift_id": str(theirs.logical_shift_id),
                }
            },
        ),
        Fixture(
            "me.shift_requests",
            "getMyShiftRequests",
            "GET",
            "/v2/me/shift-requests",
            staff,
            200,
            s.ShiftRequestList(items=[swap_open, claim]),
        ),
        Fixture(
            "shift_request.accept",
            "acceptShiftRequest",
            "POST",
            "/v2/shift-requests/{request_id}/accept",
            "staff_ravi",
            200,
            swap_pending,
            swap_path,
        ),
        Fixture(
            "shift_request.cancel",
            "cancelShiftRequest",
            "POST",
            "/v2/shift-requests/{request_id}/cancel",
            staff,
            200,
            swap_open.model_copy(update={"status": "cancelled"}),
            swap_path,
        ),
        Fixture(
            "shift_requests.list",
            "listShiftRequests",
            "GET",
            "/v2/outlets/{outlet_id}/shift-requests",
            manager,
            200,
            s.ShiftRequestList(items=[swap_pending, claim]),
            {"path_params": {"outlet_id": str(HOME)}, "query": {"status": "pending_manager"}},
        ),
        Fixture(
            "shift_request.approve",
            "approveShiftRequest",
            "POST",
            "/v2/shift-requests/{request_id}/approve",
            manager,
            200,
            approved,
            by_id,
        ),
        Fixture(
            "shift_request.approve.stale",
            "approveShiftRequest",
            "POST",
            "/v2/shift-requests/{request_id}/approve",
            manager,
            200,
            claim.model_copy(update={"status": "stale", **decided}),
            by_id,
        ),
        Fixture(
            "shift_request.approve.invalid",
            "approveShiftRequest",
            "POST",
            "/v2/shift-requests/{request_id}/approve",
            manager,
            200,
            swap_pending.model_copy(update={"status": "invalid", "violations": [rest], **decided}),
            swap_path,
        ),
        Fixture(
            "shift_request.reject",
            "rejectShiftRequest",
            "POST",
            "/v2/shift-requests/{request_id}/reject",
            manager,
            200,
            claim.model_copy(update={"status": "rejected", **decided}),
            by_id,
        ),
    ]


def p10_fixtures(published: s.ScheduleVersion) -> list[Fixture]:
    """Ravi asks to stop working Wednesdays; the preview names the published Wednesday shift."""
    ravi = uid("employee", "ravi")
    emp = world_snapshot.build("indiranagar", WEEK).employees[ravi]
    current = [
        s.AvailabilityWindow.model_validate(
            {"weekday": w.weekday, "start_minute": w.start_minute, "end_minute": w.end_minute, "kind": w.kind}
        )
        for w in sorted(emp.windows, key=lambda w: (w.weekday, w.start_minute, w.kind))
    ]
    proposed = [w for w in current if w.weekday != 2]
    broken = {
        h.logical_id
        for h in sched_availability.impact(
            [Window(w.weekday, w.start_minute, w.end_minute, w.kind) for w in proposed],
            [_to_model(y) for y in published.shifts if y.employee_id == ravi],
            IST,
        )
    }
    hits = [sh for sh in published.shifts if sh.logical_shift_id in broken]
    affected = [
        s.AffectedShift(
            schedule_id=published.schedule_id,
            version_id=published.id,
            logical_shift_id=h.logical_shift_id,
            outlet_id=h.outlet_id,
            skill_id=h.skill_id,
            start_at=h.start_at,
            end_at=h.end_at,
            locked=h.locked,
        )
        for h in hits
    ]
    req = s.AvailabilityRequestView(
        id=uid("availability_request", "ravi:no-wednesdays"),
        employee_id=ravi,
        status="pending",
        base_revision=1,
        windows=proposed,
        current=current,
        note="Evening classes on Wednesdays",
        created_at=stamp("2026-10-18T09:30:00"),
        decided_by_user_id=None,
        decided_at=None,
        affected=affected,
    )
    decided = {
        "decided_by_user_id": uid("user", "manager_indiranagar"),
        "decided_at": stamp("2026-10-18T12:00:00"),
    }
    accepted = req.model_copy(update={"status": "accepted", "current": proposed, **decided})
    path = {"path_params": {"request_id": str(req.id)}}
    manager, staff = "manager_indiranagar", "staff_ravi"
    return [
        Fixture(
            "availability_request.create",
            "createAvailabilityRequest",
            "POST",
            "/v2/me/availability-requests",
            staff,
            201,
            req,
            {
                "body": {
                    "base_revision": 1,
                    "windows": [w.model_dump() for w in proposed],
                    "note": "Evening classes on Wednesdays",
                }
            },
        ),
        Fixture(
            "me.availability_requests",
            "getMyAvailabilityRequests",
            "GET",
            "/v2/me/availability-requests",
            staff,
            200,
            s.AvailabilityRequestList(items=[req]),
        ),
        Fixture(
            "availability_request.get",
            "getAvailabilityRequest",
            "GET",
            "/v2/availability-requests/{request_id}",
            manager,
            200,
            req,
            path,
        ),
        Fixture(
            "availability_requests.list",
            "listAvailabilityRequests",
            "GET",
            "/v2/outlets/{outlet_id}/availability-requests",
            manager,
            200,
            s.AvailabilityRequestList(items=[req]),
            {"path_params": {"outlet_id": str(HOME)}, "query": {"status": "pending"}},
        ),
        Fixture(
            "availability_request.accept",
            "acceptAvailabilityRequest",
            "POST",
            "/v2/availability-requests/{request_id}/accept",
            manager,
            200,
            accepted,
            path,
        ),
        Fixture(
            "availability_request.accept.stale",
            "acceptAvailabilityRequest",
            "POST",
            "/v2/availability-requests/{request_id}/accept",
            manager,
            409,
            error(
                "stale_version",
                "This person's availability changed after the request. Ask them to send it again.",
                current_revision=2,
            ),
            path,
        ),
        Fixture(
            "availability_request.reject",
            "rejectAvailabilityRequest",
            "POST",
            "/v2/availability-requests/{request_id}/reject",
            manager,
            200,
            req.model_copy(update={"status": "rejected", **decided}),
            path,
        ),
        Fixture(
            "availability_request.cancel",
            "cancelAvailabilityRequest",
            "POST",
            "/v2/availability-requests/{request_id}/cancel",
            staff,
            200,
            req.model_copy(update={"status": "cancelled"}),
            path,
        ),
    ]


def p4_fixtures(published: s.ScheduleVersion) -> list[Fixture]:
    wednesday = WEEK + timedelta(days=2)
    hit = next(
        sh
        for sh in published.shifts
        if sh.employee_id and not sh.locked and sh.start_at.astimezone(IST).date() == wednesday
    )
    employee = hit.employee_id
    assert employee is not None
    absence_id = uid("absence", f"sick:{employee}:{wednesday}")
    mark = s.AbsenceMark(
        id=absence_id,
        employee_id=employee,
        start_at=at(wednesday, 0),
        end_at=at(wednesday, 1440),
        kind="sick",
        status="confirmed",
    )
    affected = [
        s.AffectedShift(
            schedule_id=published.schedule_id,
            version_id=published.id,
            logical_shift_id=hit.logical_shift_id,
            outlet_id=hit.outlet_id,
            skill_id=hit.skill_id,
            start_at=hit.start_at,
            end_at=hit.end_at,
            locked=False,
        )
    ]
    repair_run = uid("run", f"repair:{absence_id}")
    report = s.AbsenceReport(
        absence=mark, affected=affected, lock_conflicts=[], repair_suggested=True, repair_run_ids=[repair_run]
    )
    ravi = uid("employee", "ravi")
    requested = s.AbsenceMark(
        id=uid("absence", f"leave:{ravi}"),
        employee_id=ravi,
        start_at=at(WEEK + timedelta(days=4), 0),
        end_at=at(WEEK + timedelta(days=5), 0),
        kind="leave",
        status="requested",
    )

    def overlapping(emp: uuid.UUID, start: Any, end: Any) -> list[s.AffectedShift]:
        return [
            s.AffectedShift(
                schedule_id=published.schedule_id,
                version_id=published.id,
                logical_shift_id=sh.logical_shift_id,
                outlet_id=sh.outlet_id,
                skill_id=sh.skill_id,
                start_at=sh.start_at,
                end_at=sh.end_at,
                locked=sh.locked,
            )
            for sh in published.shifts
            if sh.employee_id == emp and sh.start_at < end and sh.end_at > start
        ]

    leave_hits = overlapping(ravi, requested.start_at, requested.end_at)
    leave_locked = [h.logical_shift_id for h in leave_hits if h.locked]
    leave_repair = uid("run", f"repair:{requested.id}")

    def requested_report(status: str) -> s.AbsenceReport:
        hits = leave_hits if status == "confirmed" else []
        return s.AbsenceReport(
            absence=s.AbsenceMark.model_validate(requested.model_dump() | {"status": status}),
            affected=hits,
            lock_conflicts=leave_locked if hits else [],
            repair_suggested=bool(hits),
            repair_run_ids=[leave_repair] if any(not h.locked for h in hits) else [],
        )

    # The repair's chosen plan: the same week with the absent employee's Wednesday shift handed to the
    # colleague the replacement recommender ranks first (so the two fixtures tell one story).
    base = [_to_model(sh) for sh in published.shifts]
    rec = sched_recommend.recommend(
        world_snapshot.build("indiranagar", WEEK, with_bench=True), base, hit.logical_shift_id, "balanced"
    )
    cover = rec.options[0].employee_id
    repaired = [
        replace(sh, employee_id=cover) if sh.logical_id == hit.logical_shift_id else sh for sh in base
    ]
    repair_key = f"indiranagar:{WEEK}:repair:{absence_id}"
    repaired_eval = _evaluated(repaired)
    moved = next(sh for sh in repaired if sh.logical_id == hit.logical_shift_id)
    repair_trace, repair_rows, repair_why = sched_trace.build(
        world_snapshot.build("indiranagar", WEEK, with_bench=True),
        "least_disruption",
        base,
        repaired,
        exclude=frozenset({employee}),
    )
    repair_candidate = s.Candidate(
        id=uid("candidate", f"repair:{absence_id}:1"),
        rank=1,
        strategy="least_disruption",
        solver_status="OPTIMAL",
        proven_optimal=True,
        materialized_version_id=None,
        metrics=repaired_eval["metrics"],
        changed_shifts=1,
        validation=repaired_eval["validation"],
        disruption=s.Disruption(changed_shifts=1, added_shifts=0, cross_outlet_moves=0, open_shifts=0),
        explanations=[s.ShiftExplanation.model_validate(e) for e in repair_why],
        trace=s.DecisionTrace.model_validate(repair_trace),
    )
    repair_detail = s.CandidateDetail.model_validate(
        repair_candidate.model_dump()
        | {
            "run_id": repair_run,
            "base_version_id": published.id,
            "diff": {
                "added": [],
                "changed": [
                    s.CandidateShift.model_validate(
                        _to_contract(moved, repair_key).model_dump(exclude={"id", "lock_reason"})
                    )
                ],
                "removed": [],
            },
            "trace_changes": repair_rows,
        }
    )

    def fact(r: Any) -> s.ExplanationFact:
        return s.ExplanationFact(code=r.code, ok=r.ok, message=r.message, facts=r.facts)

    recommended = s.ReplacementRecommendations(
        version_id=published.id,
        version_status="published",
        shift=hit,
        vacating_employee_id=employee,
        profile="balanced",
        policy_version=sched_recommend.POLICY_VERSION,
        considered=rec.considered,
        eligible=rec.eligible,
        recommendations=[
            s.Recommendation(
                rank=i,
                employee_id=o.employee_id,
                name=o.name,
                home_outlet_id=o.home_outlet_id,
                disruption_class=o.disruption_class,  # type: ignore[arg-type]
                incremental_cost=s.Money(amount_paise=o.incremental_cost_paise),
                overtime_minutes_added=max(0, o.overtime_minutes_added),
                fairness_delta=o.fairness_delta,
                weekly_minutes_after=o.weekly_minutes_after,
                within_preferred_window=o.within_preferred_window,
                reasons=[fact(r) for r in o.reasons],
                edit=s.UpdateShift(
                    op="update", logical_shift_id=hit.logical_shift_id, employee_id=o.employee_id
                ),
            )
            for i, o in enumerate(rec.options, start=1)
        ],
        rejected=[
            s.AlternativeFact(
                employee_id=a.employee_id,
                name=a.name,
                status="rejected",
                reasons=[fact(r) for r in a.reasons],
            )
            for a in rec.rejected
        ],
    )
    rec_req = {
        "body": {
            "version_id": str(published.id),
            "logical_shift_id": str(hit.logical_shift_id),
            "profile": "balanced",
            "include_other_outlets": False,
            "limit": 5,
        }
    }
    repair_draft = s.ScheduleVersion(
        id=uid("version", repair_key),
        schedule_id=published.schedule_id,
        version_number=published.version_number + 1,
        status="draft",
        source="repair",
        reason="Selected option 1 (least disruption)",
        base_version_id=published.id,
        optimization_run_id=repair_run,
        created_by_user_id=uid("user", "manager_indiranagar"),
        approved_by_user_id=None,
        created_at=stamp("2026-10-21T16:24:10"),
        published_at=None,
        revision=1,
        input_hash="sha256:" + uuid.uuid5(NS, "input:repair").hex,
        shifts=[_to_contract(sh, repair_key) for sh in repaired],
        **repaired_eval,
        recorded_metrics=repaired_eval["metrics"],
    )
    body = {
        "employee_id": str(employee),
        "start_at": mark.start_at.isoformat(),
        "end_at": mark.end_at.isoformat(),
        "kind": "sick",
        "status": "confirmed",
        "reason": None,
    }
    queued = s.OptimizationRun(
        id=repair_run,
        kind="repair",
        outlet_ids=[HOME],
        base_version_ids=[published.id],
        strategy="least_disruption",
        absence_id=absence_id,
        job_state="queued",
        solver_status=None,
        input_hash="sha256:" + uuid.uuid5(NS, "input:repair").hex,
        queued_at=stamp("2026-10-21T16:21:00"),
        started_at=None,
        finished_at=None,
        solver_wall_ms=None,
        poll_after_ms=300,
        candidates=[],
        infeasibility=None,
        error=None,
    )
    # Scenario Lab (v4 section 23): "What if they call in sick on Wednesday and Saturday evening is 30%
    # busier?" The baseline is the published week under those events; the plan converted is the repaired
    # roster, re-checked against current facts.
    scenario_id = uid("scenario", "sick-and-busy")
    scenario_run_id = uid("run", "scenario:sick-and-busy")
    sick_event = {
        "type": "absence",
        "payload": {
            "employee_id": str(employee),
            "start_at": at(wednesday, 0).isoformat(),
            "end_at": at(wednesday, 1440).isoformat(),
        },
    }
    busy_event = {"type": "demand_change", "payload": {"percent": 30, "weekdays": [5], "start_minute": 1080}}
    what_if = sched_scenario.apply(
        world_snapshot.build("indiranagar", WEEK, with_bench=True),
        [sched_scenario.Event(e["type"], e["payload"]) for e in (sick_event, busy_event)],  # type: ignore[arg-type]
    )
    hard = [v for v in sched_validator.validate(what_if, base).violations if v.severity == "hard"]
    scenario_events = [
        s.ScenarioEvent(id=uid("scenario_event", f"sick-and-busy:{n}"), sequence=n, **e)  # type: ignore[arg-type]
        for n, e in enumerate((sick_event, busy_event), start=1)
    ]
    scenario_common: dict[str, Any] = dict(
        id=scenario_id,
        outlet_id=HOME,
        week_start=WEEK,
        schedule_id=published.schedule_id,
        title="Sick on Wednesday, busy Saturday evening",
        base_version_id=published.id,
        created_by_user_id=uid("user", "manager_indiranagar"),
        created_at=stamp("2026-10-21T17:00:00"),
        expires_at=stamp("2026-10-28T17:00:00"),
        converted_version_id=None,
        events=scenario_events,
    )
    scenario_new = s.Scenario(status="open", latest_run_id=None, baseline=None, **scenario_common)
    scenario_ran = s.Scenario(
        status="open",
        latest_run_id=scenario_run_id,
        baseline=s.ScenarioBaseline(
            run_id=scenario_run_id,
            metrics=s.Metrics.model_validate(sched_metrics.as_contract(sched_metrics.compute(what_if, base))),
            hard_violations=len(hard),
            violation_codes=sorted({v.code for v in hard}),
        ),
        **scenario_common,
    )
    scenario_queued = queued.model_copy(
        update={
            "id": scenario_run_id,
            "kind": "scenario",
            "strategy": "balanced",
            "absence_id": None,
            "scenario_id": scenario_id,
            "input_hash": "sha256:" + uuid.uuid5(NS, "input:scenario").hex,
            "poll_after_ms": 500,
        }
    )
    scenario_key = f"indiranagar:{WEEK}:scenario:sick-and-busy"
    scenario_draft = repair_draft.model_copy(
        update={
            "id": uid("version", scenario_key),
            "source": "scenario",
            "reason": "Selected option 1 (balanced)",
            "optimization_run_id": scenario_run_id,
            "created_at": stamp("2026-10-21T17:05:00"),
            "input_hash": scenario_queued.input_hash,
            "shifts": [_to_contract(sh, scenario_key) for sh in repaired],
        }
    )
    scenario_candidate = uid("candidate", "scenario:sick-and-busy:1")
    widened = queued.model_copy(
        update={
            "job_state": "succeeded",
            "solver_status": "OPTIMAL",
            "started_at": stamp("2026-10-21T16:21:00.300"),
            "finished_at": stamp("2026-10-21T16:21:02.900"),
            "solver_wall_ms": 2480,
            "poll_after_ms": None,
            "candidates": [repair_candidate],
            "repair_stages": [
                s.RepairStage(
                    stage="impact",
                    result="insufficient",
                    free_shifts=1,
                    pool=12,
                    minimum_shortfall_minutes=240,
                    released="only the shifts the absence breaks",
                ),
                s.RepairStage(
                    stage="same_day",
                    result="insufficient",
                    free_shifts=8,
                    pool=12,
                    minimum_shortfall_minutes=240,
                    released="shifts from Wednesday 09:00",
                    widened_because="impact left 240 staff-minutes below minimum staffing",
                ),
                s.RepairStage(
                    stage="adjacent_shifts",
                    result="selected",
                    free_shifts=24,
                    pool=12,
                    minimum_shortfall_minutes=0,
                    released="the day before and after too",
                    widened_because="same_day left 240 staff-minutes below minimum staffing",
                ),
            ],
        }
    )
    repair_path = "/v2/outlets/{outlet_id}/schedules/{week_start}/repair"
    published_note = s.Notification(
        id=uid("notification", f"published:{published.id}:ravi"),
        topic="schedule.published",
        title=f"Your schedule for the week of {WEEK:%d %b} was published.",
        payload={"schedule_id": str(published.schedule_id), "version_id": str(published.id)},
        delivered_at=stamp("2026-10-17T15:14:05"),
        read_at=None,
    )
    repair_req: dict[str, Any] = {
        "path_params": {"outlet_id": str(HOME), "week_start": WEEK.isoformat()},
        "headers": {"Idempotency-Key": "repair-c41a77e0"},
        "body": {
            "absence_id": str(absence_id),
            "base_version_id": str(published.id),
            "unlock_logical_shift_ids": [],
            "time_limit_seconds": 3,
        },
    }
    return [
        Fixture(
            "scenario.create",
            "createScenario",
            "POST",
            "/v2/outlets/{outlet_id}/schedules/{week_start}/scenarios",
            "manager_indiranagar",
            201,
            scenario_new.model_copy(update={"events": scenario_events[:1]}),
            {
                "path_params": {"outlet_id": str(HOME), "week_start": WEEK.isoformat()},
                "body": {"title": scenario_new.title, "events": [sick_event]},
            },
        ),
        Fixture(
            "scenario.create.invalid_event",
            "createScenario",
            "POST",
            "/v2/outlets/{outlet_id}/schedules/{week_start}/scenarios",
            "manager_indiranagar",
            422,
            error(
                "validation_failed",
                "Some fields need attention.",
                fields=[
                    {
                        "path": ["events", 0, "type"],
                        "message": "Unsupported scenario event. Supported: "
                        + ", ".join(sched_scenario.EVENT_TYPES)
                        + ".",
                    }
                ],
            ),
            {
                "path_params": {"outlet_id": str(HOME), "week_start": WEEK.isoformat()},
                "body": {"title": "Rain", "events": [{"type": "weather", "payload": {"rain_mm": 40}}]},
            },
        ),
        Fixture(
            "scenario.event.add",
            "addScenarioEvent",
            "POST",
            "/v2/scenarios/{scenario_id}/events",
            "manager_indiranagar",
            201,
            scenario_new,
            {"path_params": {"scenario_id": str(scenario_id)}, "body": busy_event},
        ),
        Fixture(
            "scenarios.list",
            "listScenarios",
            "GET",
            "/v2/outlets/{outlet_id}/scenarios",
            "manager_indiranagar",
            200,
            s.ScenarioList(items=[scenario_ran]),
            {"path_params": {"outlet_id": str(HOME)}, "query": {"week_start": WEEK.isoformat()}},
        ),
        Fixture(
            "scenario.discard",
            "discardScenario",
            "POST",
            "/v2/scenarios/{scenario_id}/discard",
            "manager_indiranagar",
            200,
            scenario_ran.model_copy(update={"status": "discarded"}),
            {"path_params": {"scenario_id": str(scenario_id)}},
        ),
        Fixture(
            "scenario.run.accepted",
            "runScenario",
            "POST",
            "/v2/scenarios/{scenario_id}/run",
            "manager_indiranagar",
            202,
            scenario_queued,
            {
                "path_params": {"scenario_id": str(scenario_id)},
                "headers": {"Idempotency-Key": "scenario-run-4e1a"},
                "body": {"strategy": "balanced", "time_limit_seconds": 10},
            },
        ),
        Fixture(
            "scenario.get",
            "getScenario",
            "GET",
            "/v2/scenarios/{scenario_id}",
            "manager_indiranagar",
            200,
            scenario_ran,
            {"path_params": {"scenario_id": str(scenario_id)}},
        ),
        Fixture(
            "scenario.convert",
            "convertScenario",
            "POST",
            "/v2/scenarios/{scenario_id}/convert",
            "manager_indiranagar",
            201,
            scenario_draft,
            {
                "path_params": {"scenario_id": str(scenario_id)},
                "headers": {"Idempotency-Key": "scenario-convert-77c2"},
                "body": {"candidate_id": str(scenario_candidate)},
            },
        ),
        Fixture(
            "scenario.convert.assumptions",
            "convertScenario",
            "POST",
            "/v2/scenarios/{scenario_id}/convert",
            "manager_indiranagar",
            409,
            error(
                "conflict",
                "This plan only works under the scenario's assumptions; current facts break it. "
                "Generate against the real week instead.",
                hard_violations=2,
                violation_codes=["minimum_coverage"],
            ),
            {
                "path_params": {"scenario_id": str(scenario_id)},
                "headers": {"Idempotency-Key": "scenario-convert-91ab"},
                "body": {"candidate_id": str(scenario_candidate)},
            },
        ),
        Fixture(
            "candidate.select.scenario",
            "selectOptimizationCandidate",
            "POST",
            "/v2/optimization-candidates/{candidate_id}/select",
            "manager_indiranagar",
            409,
            error(
                "conflict",
                "This plan is a what-if. Turn it into a plan from its scenario instead.",
                scenario_id=str(scenario_id),
            ),
            {
                "path_params": {"candidate_id": str(scenario_candidate)},
                "headers": {"Idempotency-Key": "select-scenario-0d3f"},
            },
        ),
        Fixture(
            "absence.report",
            "reportAbsence",
            "POST",
            "/v2/absences",
            "manager_indiranagar",
            201,
            report,
            {"headers": {"Idempotency-Key": "absence-5a1e09c3"}, "body": body},
        ),
        Fixture(
            "absence.report.requested",
            "reportAbsence",
            "POST",
            "/v2/absences",
            "staff_ravi",
            201,
            s.AbsenceReport(
                absence=requested, affected=leave_hits, lock_conflicts=leave_locked, repair_suggested=False
            ),
            {
                "headers": {"Idempotency-Key": "absence-77b2d1f0"},
                "body": {
                    "employee_id": str(ravi),
                    "start_at": requested.start_at.isoformat(),
                    "end_at": requested.end_at.isoformat(),
                    "kind": "leave",
                    "status": "requested",
                    "reason": "Family function",
                },
            },
        ),
        Fixture(
            "me.notifications",
            "getMyNotifications",
            "GET",
            "/v2/me/notifications",
            "staff_ravi",
            200,
            s.NotificationList(items=[published_note]),
            {"query": {"unread_only": "true"}},
        ),
        Fixture(
            "me.notifications.read",
            "markNotificationRead",
            "POST",
            "/v2/me/notifications/{notification_id}/read",
            "staff_ravi",
            200,
            published_note.model_copy(update={"read_at": stamp("2026-10-17T18:30:00")}),
            {"path_params": {"notification_id": str(published_note.id)}},
        ),
        Fixture(
            "me.absences",
            "getMyAbsences",
            "GET",
            "/v2/me/absences",
            "staff_ravi",
            200,
            s.AbsenceList(items=[requested]),
            {"query": {"from": WEEK.isoformat() + "T00:00:00+05:30"}},
        ),
        Fixture(
            "absences.list",
            "listAbsences",
            "GET",
            "/v2/absences",
            "manager_indiranagar",
            200,
            s.AbsenceList(items=[mark, requested]),
            {"query": {"outlet_id": str(HOME), "from": WEEK.isoformat() + "T00:00:00+05:30"}},
        ),
        Fixture(
            "absence.update.confirm",
            "updateAbsence",
            "PATCH",
            "/v2/absences/{absence_id}",
            "manager_indiranagar",
            200,
            report,
            {"path_params": {"absence_id": str(absence_id)}, "body": {"status": "confirmed"}},
        ),
        *[
            Fixture(
                f"absence.update.requested.{verb}",
                "updateAbsence",
                "PATCH",
                "/v2/absences/{absence_id}",
                persona,
                200,
                requested_report(status),
                {"path_params": {"absence_id": str(requested.id)}, "body": {"status": status}},
            )
            for verb, status, persona in (
                ("confirm", "confirmed", "manager_indiranagar"),
                ("reject", "rejected", "manager_indiranagar"),
                ("cancel", "cancelled", "staff_ravi"),
            )
        ],
        Fixture(
            "absence.update.withdraw_conflict",
            "updateAbsence",
            "PATCH",
            "/v2/absences/{absence_id}",
            "staff_ravi",
            409,
            error("conflict", "Only a request that is still waiting can be withdrawn. Ask your manager."),
            {"path_params": {"absence_id": str(requested.id)}, "body": {"status": "cancelled"}},
        ),
        Fixture(
            "absence.update.already_closed",
            "updateAbsence",
            "PATCH",
            "/v2/absences/{absence_id}",
            "manager_indiranagar",
            409,
            error("conflict", "This absence was already rejected."),
            {"path_params": {"absence_id": str(requested.id)}, "body": {"status": "confirmed"}},
        ),
        Fixture(
            "candidate.detail.repair",
            "getOptimizationCandidate",
            "GET",
            "/v2/optimization-candidates/{candidate_id}",
            "manager_indiranagar",
            200,
            repair_detail,
            {"path_params": {"candidate_id": str(repair_candidate.id)}},
        ),
        Fixture(
            "recommendations.replacements",
            "recommendReplacements",
            "POST",
            "/v2/recommendations/replacements",
            "manager_indiranagar",
            200,
            recommended,
            rec_req,
        ),
        Fixture(
            "recommendations.replacements.other_outlets.manager",
            "recommendReplacements",
            "POST",
            "/v2/recommendations/replacements",
            "manager_indiranagar",
            403,
            error("permission_denied", "Only an owner can borrow staff from other outlets."),
            {"body": {**rec_req["body"], "include_other_outlets": True}},
        ),
        Fixture(
            "recommendations.replacements.unknown_shift",
            "recommendReplacements",
            "POST",
            "/v2/recommendations/replacements",
            "manager_indiranagar",
            422,
            error(
                "validation_failed",
                "Some fields need attention.",
                fields=[{"path": ["logical_shift_id"], "message": "That shift is not in this version."}],
            ),
            {"body": {**rec_req["body"], "logical_shift_id": str(uid("logical_shift", "not-in-week"))}},
        ),
        Fixture(
            "candidate.select.repair",
            "selectOptimizationCandidate",
            "POST",
            "/v2/optimization-candidates/{candidate_id}/select",
            "manager_indiranagar",
            201,
            repair_draft,
            {
                "path_params": {"candidate_id": str(repair_candidate.id)},
                "headers": {"Idempotency-Key": "select-repair-61d0b4a2"},
            },
        ),
        Fixture(
            "repair.accepted",
            "repairSchedule",
            "POST",
            repair_path,
            "manager_indiranagar",
            202,
            queued,
            repair_req,
        ),
        Fixture(
            "run.repair.widened",
            "getOptimizationRun",
            "GET",
            "/v2/optimization-runs/{run_id}",
            "manager_indiranagar",
            200,
            widened,
            {"path_params": {"run_id": str(repair_run)}},
        ),
        Fixture(
            "repair.cross_outlet.manager",
            "repairSchedule",
            "POST",
            repair_path,
            "manager_indiranagar",
            403,
            error("permission_denied", "Only an owner can let a repair borrow staff from other outlets."),
            {**repair_req, "body": {**repair_req["body"], "allow_cross_outlet": True}},
        ),
        Fixture(
            "repair.freeze_conflict",
            "repairSchedule",
            "POST",
            repair_path,
            "manager_indiranagar",
            409,
            error(
                "conflict",
                "A current fact breaks a shift you asked to keep. Unfreeze it or authorize the change.",
                frozen_logical_shift_ids=[str(hit.logical_shift_id)],
            ),
            {
                **repair_req,
                "body": {
                    **repair_req["body"],
                    "freeze": {"shift_ids": [str(hit.logical_shift_id)], "employee_ids": [], "days": []},
                },
            },
        ),
        Fixture(
            "repair.locked",
            "repairSchedule",
            "POST",
            repair_path,
            "manager_indiranagar",
            409,
            error(
                "conflict",
                "The absence hits a locked shift. Authorize changing it to repair.",
                locked_logical_shift_ids=[str(hit.logical_shift_id)],
            ),
            repair_req,
        ),
    ]


# ---------------------------------------------------------------- contract 3.0: proposals (v3 section 31)


def proposal_fixtures(draft: s.ScheduleVersion) -> list[Fixture]:
    """Proposal of the selected-candidate draft and each publication outcome of approving it."""
    manager = uid("user", "manager_indiranagar")
    proposal = s.Proposal(
        id=uid("proposal", f"{draft.id}:1"),
        schedule_id=draft.schedule_id,
        draft_version_id=draft.id,
        draft_revision=draft.revision,
        base_version_id=draft.base_version_id,
        candidate_id=uid("candidate", "1:OPTIMAL"),
        status="pending",
        metrics_at_proposal=draft.metrics,
        requested_by_user_id=manager,
        decided_by_user_id=None,
        created_at=stamp("2026-10-18T19:45:00"),
        decided_at=None,
        expires_at=stamp("2026-10-19T19:45:00"),
    )

    def decided(status: s.ProposalStatus) -> s.Proposal:
        return proposal.model_copy(
            update={
                "status": status,
                "decided_by_user_id": manager,
                "decided_at": stamp("2026-10-18T19:52:00"),
            }
        )

    shift = next(sh for sh in draft.shifts if sh.employee_id)
    assert shift.employee_id is not None
    absent = s.Violation(
        code="absent",
        severity="hard",
        message="This employee has a confirmed absence during this shift.",
        employee_id=shift.employee_id,
        logical_shift_ids=[shift.logical_shift_id],
        facts={"absence_kind": "sick"},
    )
    agreed = draft.metrics.model_dump(mode="json")
    cost = agreed["labour_cost"]["amount_paise"]
    now = agreed | {"labour_cost": {"amount_paise": cost + max(15_000, cost // 20), "currency": "INR"}}
    deltas = [s.MetricDelta.model_validate(d) for d in sched_metrics.material_changes(agreed, now)]
    path = "/v2/proposals/{proposal_id}/approve"

    def approve(key: str, acknowledge: bool = False) -> dict[str, Any]:
        return {
            "path_params": {"proposal_id": str(proposal.id)},
            "headers": {"Idempotency-Key": key},
            "body": {"acknowledge_changes": acknowledge},
        }

    published = _summary(
        draft,
        status="published",
        approved_by_user_id=manager,
        published_at=stamp("2026-10-18T19:52:00"),
    )
    # Publication stores the metrics measured against current facts, so the acknowledged story publishes
    # the moved cost the manager accepted, not the cost at proposal time.
    published_acknowledged = published.model_copy(update={"recorded_metrics": s.Metrics.model_validate(now)})
    return [
        Fixture(
            "proposal.create",
            "createProposal",
            "POST",
            "/v2/proposals",
            "manager_indiranagar",
            201,
            proposal,
            {
                "headers": {"Idempotency-Key": "propose-61c0d4a8"},
                "body": {"draft_version_id": str(draft.id), "expected_revision": draft.revision},
            },
        ),
        Fixture(
            "proposals.list.pending",
            "listProposals",
            "GET",
            "/v2/proposals",
            "manager_indiranagar",
            200,
            s.ProposalList(items=[proposal]),
            {"query": {"schedule_id": str(draft.schedule_id), "status": "pending"}},
        ),
        Fixture(
            "proposal.get",
            "getProposal",
            "GET",
            "/v2/proposals/{proposal_id}",
            "manager_indiranagar",
            200,
            proposal,
            {"path_params": {"proposal_id": str(proposal.id)}},
        ),
        Fixture(
            "proposal.approve.published",
            "approveProposal",
            "POST",
            path,
            "manager_indiranagar",
            200,
            s.ProposalDecision(
                outcome="published",
                message="Published.",
                proposal=decided("approved"),
                published=published,
                superseded_version_id=None,
            ),
            approve("approve-0f3a7b19"),
        ),
        Fixture(
            "proposal.approve.stale",
            "approveProposal",
            "POST",
            path,
            "manager_indiranagar",
            200,
            s.ProposalDecision(
                outcome="stale",
                message=STALE_PUBLISHED,
                proposal=decided("stale"),
                current_version_id=uid("version", f"indiranagar:{NEXT_WEEK}:other"),
            ),
            approve("approve-5d21e8c4"),
        ),
        Fixture(
            "proposal.approve.invalid",
            "approveProposal",
            "POST",
            path,
            "manager_indiranagar",
            200,
            s.ProposalDecision(
                outcome="invalid",
                message=f"This recommendation is no longer valid: {absent.message}",
                proposal=decided("failed"),
                violations=[absent],
            ),
            approve("approve-9b47c2e0"),
        ),
        Fixture(
            "proposal.approve.changed",
            "approveProposal",
            "POST",
            path,
            "manager_indiranagar",
            200,
            s.ProposalDecision(
                outcome="changed",
                message=" ".join(d.message for d in deltas) + " Approve again to accept.",
                proposal=proposal,
                deltas=deltas,
            ),
            approve("approve-2e8f6a13"),
        ),
        Fixture(
            "proposal.approve.acknowledged",
            "approveProposal",
            "POST",
            path,
            "manager_indiranagar",
            200,
            s.ProposalDecision(
                outcome="published",
                message="Published.",
                proposal=decided("approved"),
                published=published_acknowledged,
                superseded_version_id=None,
            ),
            approve("approve-7c5d0b96", acknowledge=True),
        ),
        Fixture(
            "proposal.approve.already_decided",
            "approveProposal",
            "POST",
            path,
            "manager_indiranagar",
            409,
            error("conflict", "This proposal is already approved.", status="approved"),
            approve("approve-3a91f7d5"),
        ),
        Fixture(
            "proposal.reject",
            "rejectProposal",
            "POST",
            "/v2/proposals/{proposal_id}/reject",
            "manager_indiranagar",
            200,
            decided("rejected"),
            {"path_params": {"proposal_id": str(proposal.id)}},
        ),
    ]


# ---------------------------------------------------------------- B5.4: employee CSV onboarding (v3 s19)


def import_fixtures() -> list[Fixture]:
    from api.v2.imports import template
    from importer.employees_csv import COLUMNS

    header = ",".join(COLUMNS)
    week = ",".join(["10:00", "22:00"] * 5 + [""] * 4)
    newline = chr(10)
    good = newline.join(
        [
            header,
            f"Asha Nair,Indiranagar,Grill;Prep,190,48,40,{week}",
            f"Dev Sharma,indiranagar,Server,170,40,,{week}",
        ]
    )
    bad = newline.join(
        [
            header,
            f"Asha Nair,Mars,Grill;Juggling,190,48,40,{week}",
            f"Dev Sharma,indiranagar,Server,170,40,,{week}",
        ]
    )
    job_id, bad_id = uid("import", "employees:good"), uid("import", "employees:bad")
    created, expires = stamp("2026-10-21T10:00:00"), stamp("2026-10-22T10:00:00")

    def job(i: uuid.UUID, status: Any, rows: list[s.ImportRow], committed: Any = None) -> s.ImportJob:
        return s.ImportJob(
            id=i,
            kind="employees",
            status=status,
            filename="staff.csv",
            row_count=len(rows),
            error_count=sum(1 for r in rows if r.errors),
            file_errors=[],
            created_at=created,
            expires_at=expires,
            committed_at=committed,
            rows=rows,
        )

    def row(
        n: int, name: str, outlet: uuid.UUID | None, employee: uuid.UUID | None = None, errors: Any = ()
    ) -> s.ImportRow:
        return s.ImportRow(
            row_number=n, name=name, outlet_id=outlet, errors=list(errors), employee_id=employee
        )

    staged = job(job_id, "staged", [row(2, "Asha Nair", HOME), row(3, "Dev Sharma", HOME)])
    invalid = job(
        bad_id,
        "invalid",
        [
            row(
                2,
                "Asha Nair",
                None,
                errors=[
                    s.ImportRowError(column="outlet", message="Unknown outlet 'Mars'."),
                    s.ImportRowError(column="skills", message="Unknown roles: Juggling."),
                ],
            ),
            row(3, "Dev Sharma", HOME),
        ],
    )
    committed = job(
        job_id,
        "committed",
        [
            row(2, "Asha Nair", HOME, uid("employee", "import:asha")),
            row(3, "Dev Sharma", HOME, uid("employee", "import:dev")),
        ],
        committed=stamp("2026-10-21T10:02:00"),
    )
    stage_path = "/v2/imports/employees"
    return [
        Fixture(
            "imports.template",
            "getEmployeeImportTemplate",
            "GET",
            "/v2/imports/employees/template",
            "manager_indiranagar",
            200,
            template(),
            {},
        ),
        Fixture(
            "imports.stage",
            "stageEmployeeImport",
            "POST",
            stage_path,
            "manager_indiranagar",
            201,
            staged,
            {
                "headers": {"Idempotency-Key": "import-0b5f2c71"},
                "body": {"filename": "staff.csv", "content": good},
            },
        ),
        Fixture(
            "imports.stage.invalid",
            "stageEmployeeImport",
            "POST",
            stage_path,
            "manager_indiranagar",
            201,
            invalid,
            {
                "headers": {"Idempotency-Key": "import-6e19d4a3"},
                "body": {"filename": "staff.csv", "content": bad},
            },
        ),
        Fixture(
            "imports.get",
            "getImport",
            "GET",
            "/v2/imports/{import_id}",
            "manager_indiranagar",
            200,
            staged,
            {"path_params": {"import_id": str(job_id)}},
        ),
        Fixture(
            "imports.commit",
            "commitImport",
            "POST",
            "/v2/imports/{import_id}/commit",
            "manager_indiranagar",
            200,
            committed,
            {"path_params": {"import_id": str(job_id)}, "headers": {"Idempotency-Key": "commit-9a7e3b10"}},
        ),
    ]


# ---------------------------------------------------------------- B5.2: rules and precedence (v3 s21)


def rule_fixtures() -> list[Fixture]:
    students = s.RuleDefinition(
        rule_type="max_shift_end_time",
        scope_level="tag",
        scope={"tag": "student"},
        parameters={"latest_end_minute": 1260, "weekdays": [0, 1, 2, 3, 4]},
        source_text="Students must finish by 9 PM on weekdays",
    )
    rohit = uid("employee", "rohit")
    friday = s.RuleDefinition(
        rule_type="max_shift_end_time",
        scope_level="employee",
        scope={"employee_id": str(rohit)},
        parameters={"latest_end_minute": 1380, "weekdays": [4]},
        source_text="Rohit can work until 11 PM on Fridays",
    )
    rule_id = uid("rule", "students")
    stored = s.SchedulingRule(
        **students.model_dump(),
        id=rule_id,
        summary="No shift ends after 21:00 on weekdays",
        status="active",
        created_at=stamp("2026-10-21T11:00:00"),
    )
    affected = [
        s.RuleEmployee(employee_id=uid("employee", k), name=n)
        for k, n in sorted(
            (("rohit", "Rohit Verma"), ("kabir", "Kabir Malhotra"), ("yash", "Yash Chawla")),
            key=lambda t: t[1],
        )
    ]
    clean = s.RulePreview(
        rule=students, summary=stored.summary, valid=True, affected=affected, conflicts=[], impact=[]
    )
    clash = s.RulePreview(
        rule=friday,
        summary="No shift ends after 23:00 on Friday",
        valid=False,
        affected=[s.RuleEmployee(employee_id=rohit, name="Rohit Verma")],
        conflicts=[
            s.RuleConflict(
                rule_id=rule_id,
                rule_name="Students must finish by 9 PM on weekdays",
                employees=["Rohit Verma"],
                message='This conflicts with "Students must finish by 9 PM on weekdays". '
                "Rohit Verma is covered by both.",
                suggested_exception=friday.model_copy(update={"overrides_rule_id": rule_id}),
            )
        ],
        impact=[],
    )
    ravi = uid("employee", "ravi")
    saturday = at(WEEK + timedelta(days=5), 0)
    time_off = s.CommandPreview(
        status="ready",
        intent="give_time_off",
        summary="Mark Ravi Kumar off on Saturday 24 Oct (leave). 1 published shift will need cover; "
        "a repair starts after you confirm.",
        action=s.ProposedCall(
            operation_id="reportAbsence",
            method="POST",
            path="/v2/absences",
            body={
                "employee_id": str(ravi),
                "start_at": saturday.isoformat(),
                "end_at": (saturday + timedelta(days=1)).isoformat(),
                "kind": "leave",
                "status": "confirmed",
                "reason": "Give Ravi Saturday off",
            },
        ),
        affected_shift_count=1,
    )
    which = s.CommandPreview(
        status="needs_clarification",
        intent="give_time_off",
        summary="Which Ravi?",
        question="Which Ravi?",
        options=[
            s.CommandOption(employee_id=ravi, name="Ravi Kumar"),
            s.CommandOption(employee_id=uid("employee", "ravi-shetty"), name="Ravi Shetty"),
        ],
    )
    unavailable = s.CommandPreview(
        status="unavailable", summary="Language shortcuts are unavailable right now. Use the form."
    )
    command = "/v2/commands/parse"
    language_fixtures = [
        Fixture(
            "commands.parse",
            "parseCommand",
            "POST",
            command,
            "manager_indiranagar",
            200,
            time_off,
            {"body": {"text": "Give Ravi Saturday off"}},
        ),
        Fixture(
            "commands.parse.which",
            "parseCommand",
            "POST",
            command,
            "manager_indiranagar",
            200,
            which,
            {"body": {"text": "Give Ravi Saturday off"}},
        ),
        Fixture(
            "commands.parse.unavailable",
            "parseCommand",
            "POST",
            command,
            "manager_indiranagar",
            200,
            unavailable,
            {"body": {"text": "Give Ravi Saturday off"}},
        ),
        Fixture(
            "rules.parse",
            "parseRule",
            "POST",
            "/v2/rules/parse",
            "owner",
            200,
            s.RuleParse(
                status="ready",
                message=clean.summary,
                preview=clean.model_copy(
                    update={
                        "rule": students.model_copy(
                            update={"source_text": "Students cannot work later than 9 PM on weekdays"}
                        )
                    }
                ),
            ),
            {"body": {"text": "Students cannot work later than 9 PM on weekdays"}},
        ),
        Fixture(
            "rules.parse.unsupported",
            "parseRule",
            "POST",
            "/v2/rules/parse",
            "owner",
            200,
            s.RuleParse(
                status="unsupported",
                message="That rule is not supported. That kind of rule is not "
                "supported yet. Supported: latest end time, maximum days per week.",
            ),
            {"body": {"text": "Pay seniors more on Sundays"}},
        ),
    ]
    return language_fixtures + [
        Fixture(
            "rules.preview",
            "previewRule",
            "POST",
            "/v2/rules/preview",
            "owner",
            200,
            clean,
            {"body": students.model_dump(mode="json")},
        ),
        Fixture(
            "rules.preview.conflict",
            "previewRule",
            "POST",
            "/v2/rules/preview",
            "owner",
            200,
            clash,
            {"body": friday.model_dump(mode="json")},
        ),
        Fixture(
            "rules.create",
            "createRule",
            "POST",
            "/v2/rules",
            "owner",
            201,
            stored,
            {"headers": {"Idempotency-Key": "rule-4c1d7e20"}, "body": students.model_dump(mode="json")},
        ),
        Fixture("rules.list", "listRules", "GET", "/v2/rules", "owner", 200, s.RuleList(items=[stored]), {}),
        Fixture(
            "rules.archive",
            "archiveRule",
            "POST",
            "/v2/rules/{rule_id}/archive",
            "owner",
            200,
            stored.model_copy(update={"status": "archived"}),
            {"path_params": {"rule_id": str(rule_id)}},
        ),
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
