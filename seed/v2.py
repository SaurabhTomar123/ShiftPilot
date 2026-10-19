"""Scheduling v2 seed: tenant-scoped, deterministic, and ID-compatible with contracts/v2 fixtures.

    python -m seed.v2                  # (re)load both v2 demo tenants
    python -m seed.v2 --org spice-route

Loading an org first deletes that org's rows only; every other tenant (including the v1 demo
org loaded by seed.load) is untouched. Runs as the admin role; the database must be at head
(`python -m db.init`).

Spice Route Kitchens: 3 outlets, 60 employees (the 39 fixture employees plus 7 bench staff per
outlet), 5 skills, policy, templates, travel times, demand bands, 4 weeks of demand history,
staffing requirements for the published and the next week, a published week per outlet (same
schedule, outlet, employee and shift IDs as the fixtures) and a pending leave request.
Northwind Diner: a minimal second tenant for isolation tests.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Connection, Table, insert, select, text
from sqlalchemy.orm import Session

from db import models_v2  # noqa: F401  (registers v2 tables on Base.metadata)
from db.models import Base
from db.session import admin_engine
from scheduling import metrics, snapshot_db
from seed.world import (
    CLOSE,
    INTERVAL,
    NEXT_WEEK,
    OPEN,
    OUTLETS,
    SKILL,
    SKILLS,
    STAFF,
    TEMPLATES,
    TZ,
    WEEK,
    Emp,
    at,
    availability_windows,
    build_roster,
    requirement,
    shift_identity,
    stamp,
    uid,
)

SPICE = "spice-route"
NORTHWIND = "northwind"
ORGS = (SPICE, NORTHWIND)
HISTORY_WEEKS = 4
BENCH_NAMES = [
    "Aditi",
    "Bhaskar",
    "Chitra",
    "Dev",
    "Esha",
    "Gaurav",
    "Hema",
    "Irfan",
    "Jaya",
    "Kunal",
    "Leela",
    "Madhav",
    "Neela",
    "Omkar",
    "Padma",
    "Rakesh",
    "Sarita",
    "Tushar",
    "Uma",
    "Varun",
    "Wasim",
]
BENCH_SKILLS = [
    ("Server", "Barista"),
    ("Cashier",),
    ("Prep",),
    ("Server",),
    ("Barista", "Cashier"),
    ("Grill",),
    ("Server", "Cashier"),
]
TRAVEL = {("indiranagar", "koramangala"): 35, ("indiranagar", "hsr"): 40, ("koramangala", "hsr"): 20}


def bench(outlet_key: str) -> list[Emp]:
    """Seven extra staff per outlet who are not in the fixture rosters (60 employees in total)."""
    offset = [k for k, _ in OUTLETS].index(outlet_key) * 7
    return [
        Emp(
            f"{outlet_key}-bench-{i}",
            f"{BENCH_NAMES[offset + i]} {outlet_key.title()}",
            BENCH_SKILLS[i],
            153 + 3 * i,
        )
        for i in range(7)
    ]


@dataclass
class Rows:
    """Rows per table name, inserted in metadata dependency order."""

    tables: dict[str, list[dict[str, Any]]]

    def add(self, table: str, *rows: dict[str, Any]) -> None:
        self.tables.setdefault(table, []).extend(rows)


def org_rows(org_key: str, *, seed: int = 42) -> Rows:
    return spice_rows(seed) if org_key == SPICE else northwind_rows()


def _employee_row(org: Any, outlet_key: str, e: Emp, phone: str) -> dict[str, Any]:
    return {
        "id": uid("employee", e.key),
        "org_id": org,
        "outlet_id": uid("outlet", outlet_key),
        "name": e.name,
        "aliases": [],
        "job_role": e.skills[0].lower(),
        "pay_type": "hourly",
        "hourly_rate": Decimal(e.rate_rupees),
        "monthly_base": None,
        "phone": phone,
        "joined_on": date(2025, 1, 6),
        "status": "active",
        "regular_weekly_minutes": 2880,
        "max_weekly_minutes": 2880,
        "preferred_weekly_minutes": 2250 if e.preferred else None,
        "tags": list(e.tags),
        "overtime_allowed": False,
        "cross_outlet_eligible": e.key in ("arjun", "divya"),
        "revision": 1,
    }


def _people(rows: Rows, org: Any, outlet_key: str, staff: Iterable[Emp], phone_base: int) -> None:
    for i, e in enumerate(staff):
        rows.add("employees", _employee_row(org, outlet_key, e, f"+91{phone_base + i:010d}"))
        rows.add(
            "employee_skills",
            *[
                {
                    "org_id": org,
                    "employee_id": uid("employee", e.key),
                    "skill_id": SKILL[k],
                    "level": 2 if j == 0 else 1,
                }
                for j, k in enumerate(e.skills)
            ],
        )
        rows.add(
            "employee_availability",
            *[
                {
                    "id": uid("availability", f"{e.key}:{d}:{kind}"),
                    "org_id": org,
                    "employee_id": uid("employee", e.key),
                    "weekday": d,
                    "start_minute": a,
                    "end_minute": b,
                    "kind": kind,
                    "valid_from": date(2026, 1, 5),
                    "valid_to": None,
                }
                for d, a, b, kind in availability_windows(e)
            ],
        )


def _orders(rng: random.Random, weekday: int, minute: int) -> int:
    """Synthetic orders per 30 minutes: lunch and dinner peaks, busier Friday and Saturday."""
    peak = 1.0 + 1.6 * (720 <= minute < 900) + 2.4 * (1080 <= minute < 1320)
    return max(0, round(6 * peak * (1.3 if weekday in (4, 5) else 1.0) + rng.gauss(0, 2)))


def spice_rows(seed: int) -> Rows:
    org = uid("org", SPICE)
    rows = Rows({})
    rows.add("organizations", {"id": org, "name": "Spice Route Kitchens", "plan": "demo", "timezone": TZ})
    rows.add(
        "ot_rules",
        {
            "id": uid("ot_rule", SPICE),
            "org_id": org,
            "daily_threshold_hrs": Decimal(9),
            "weekly_threshold_hrs": Decimal(48),
            "multiplier": Decimal("2.0"),
        },
    )
    hours = {str(d): [[OPEN, CLOSE]] for d in range(7)}
    for key, name in OUTLETS:
        rows.add(
            "outlets",
            {
                "id": uid("outlet", key),
                "org_id": org,
                "name": name,
                "slug": key,
                "city": "Bengaluru",
                "timezone": TZ,
                "ot_rule_id": uid("ot_rule", SPICE),
                "operating_hours": hours,
            },
        )
    rows.add("skills", *[{"id": SKILL[n], "org_id": org, "name": n} for n in SKILLS])

    for n, (key, _) in enumerate(OUTLETS):
        _people(rows, org, key, [*STAFF[key], *bench(key)], 9_700_100_000 + n * 1000)

    users = [
        ("owner", "Asha Menon", "owner", None, None),
        ("manager_indiranagar", "Vikram Das", "manager", "indiranagar", None),
        ("manager_koramangala", "Nandini Rao", "manager", "koramangala", None),
        ("manager_hsr", "Arvind Kumar", "manager", "hsr", None),
        ("staff_ravi", "Ravi Kumar", "staff", "indiranagar", "ravi"),
    ]
    rows.add(
        "users",
        *[
            {
                "id": uid("user", k),
                "org_id": org,
                "outlet_id": uid("outlet", o) if o else None,
                "employee_id": uid("employee", e) if e else None,
                "name": name,
                "phone": f"+91970020{i:04d}",
                "role": role,
                "is_active": True,
            }
            for i, (k, name, role, o, e) in enumerate(users)
        ],
    )

    rows.add(
        "scheduling_policies",
        {
            "id": uid("policy", SPICE),
            "org_id": org,
            "outlet_id": None,
            "revision": 1,
            "effective_from": date(2026, 1, 5),
        },
    )
    for key, _ in OUTLETS:
        rows.add(
            "shift_templates",
            *[
                {
                    "id": uid("template", f"{key}:{t.key}"),
                    "org_id": org,
                    "outlet_id": uid("outlet", key),
                    "skill_id": None,
                    "name": t.key.title(),
                    "start_minute": t.start,
                    "duration_minutes": t.end - t.start,
                    "break_minutes": 30 if t.break_start is not None else 0,
                    "break_offset_minutes": t.break_start - t.start if t.break_start is not None else None,
                    "active": True,
                }
                for t in TEMPLATES.values()
            ],
        )
    for (a, b), minutes in TRAVEL.items():
        for x, y in ((a, b), (b, a)):
            rows.add(
                "travel_times",
                {
                    "org_id": org,
                    "from_outlet_id": uid("outlet", x),
                    "to_outlet_id": uid("outlet", y),
                    "minutes": minutes,
                },
            )
    bands = [(0, 15, 1, 1), (16, 30, 1, 2), (31, 50, 2, 3), (51, 70, 2, 4), (71, None, 3, 5)]
    rows.add(
        "demand_bands",
        *[
            {
                "id": uid("band", f"{skill}:{lo}"),
                "org_id": org,
                "outlet_id": None,
                "skill_id": SKILL[skill],
                "min_orders": lo,
                "max_orders": hi,
                "staff_minimum": mn,
                "staff_preferred": pref,
            }
            for skill in ("Grill", "Server")
            for lo, hi, mn, pref in bands
        ],
    )

    for key, _ in OUTLETS:
        rng = random.Random(f"{seed}:{key}")
        for d in range(-7 * HISTORY_WEEKS, 0):
            day = WEEK + timedelta(days=d)
            rows.add(
                "demand_inputs",
                *[
                    {
                        "org_id": org,
                        "outlet_id": uid("outlet", key),
                        "interval_start": at(day, m),
                        "source": "history",
                        "orders": _orders(rng, day.weekday(), m),
                    }
                    for m in range(OPEN, CLOSE, INTERVAL)
                ],
            )
        for week in (WEEK, NEXT_WEEK):
            for d in range(7):
                day = week + timedelta(days=d)
                for skill in ("Grill", "Prep", "Server", "Cashier"):
                    for m in range(OPEN, CLOSE, INTERVAL):
                        mn, pref = requirement(skill, day.weekday(), m)
                        if pref:
                            rows.add(
                                "staffing_requirements",
                                {
                                    "id": uid("requirement", f"{key}:{skill}:{at(day, m).isoformat()}"),
                                    "org_id": org,
                                    "outlet_id": uid("outlet", key),
                                    "skill_id": SKILL[skill],
                                    "interval_start": at(day, m),
                                    "interval_end": at(day, m + INTERVAL),
                                    "minimum_required": mn,
                                    "preferred_required": pref,
                                    "source": "band",
                                    "demand_revision": 3,
                                },
                            )
    return rows


def northwind_rows() -> Rows:
    org = uid("org", NORTHWIND)
    rows = Rows({})
    rows.add("organizations", {"id": org, "name": "Northwind Diner", "plan": "demo", "timezone": TZ})
    rows.add(
        "ot_rules",
        {
            "id": uid("ot_rule", NORTHWIND),
            "org_id": org,
            "daily_threshold_hrs": Decimal(9),
            "weekly_threshold_hrs": Decimal(48),
            "multiplier": Decimal("2.0"),
        },
    )
    rows.add(
        "outlets",
        {
            "id": uid("outlet", "northwind-main"),
            "org_id": org,
            "name": "Northwind Main",
            "slug": "main",
            "city": "Pune",
            "timezone": TZ,
            "ot_rule_id": uid("ot_rule", NORTHWIND),
            "operating_hours": {str(d): [[OPEN, CLOSE]] for d in range(7)},
        },
    )
    rows.add(
        "skills",
        *[{"id": uid("skill", f"{NORTHWIND}:{n}"), "org_id": org, "name": n} for n in ("Grill", "Server")],
    )
    staff = [
        Emp(f"nw-{i}", name, ("Grill",) if i % 2 == 0 else ("Server",), 180)
        for i, name in enumerate(("Olivia Hart", "Sam Doyle", "Mia Chen", "Leo Park"))
    ]
    for i, e in enumerate(staff):
        rows.add(
            "employees",
            _employee_row(org, "northwind-main", e, f"+91{9_700_900_000 + i:010d}")
            | {"job_role": "grill" if i % 2 == 0 else "server"},
        )
        rows.add(
            "employee_skills",
            {
                "org_id": org,
                "employee_id": uid("employee", e.key),
                "skill_id": uid("skill", f"{NORTHWIND}:{'Grill' if i % 2 == 0 else 'Server'}"),
                "level": 2,
            },
        )
    rows.add(
        "users",
        {
            "id": uid("user", f"{NORTHWIND}:owner"),
            "org_id": org,
            "outlet_id": None,
            "employee_id": None,
            "name": "Grace Hall",
            "phone": "+919700299001",
            "role": "owner",
            "is_active": True,
        },
    )
    return rows


# ---------------------------------------------------------------- database


def reset_org(conn: Connection, org_id: Any) -> None:
    """Delete one tenant's rows. Admin only. Triggers (including the immutability guards) are
    suspended for this transaction because the tenant is being removed as a whole."""
    conn.execute(text("SET LOCAL session_replication_role = replica"))
    for table in reversed(Base.metadata.sorted_tables):
        if "org_id" in table.columns:
            conn.execute(table.delete().where(table.c.org_id == org_id))
    organizations: Table = Base.metadata.tables["organizations"]
    conn.execute(organizations.delete().where(organizations.c.id == org_id))
    conn.execute(text("SET LOCAL session_replication_role = origin"))


def _measure(
    conn: Connection, org: Any, outlet_id: Any, week: date, schedule: Any, version: Any
) -> dict[str, Any]:
    """The version's metrics as the API stores them (v3 section 22), computed under the app role with
    the tenant context set, so row-level security scopes the snapshot to this organization."""
    conn.execute(text("SET LOCAL ROLE shiftpilot_app"))
    conn.execute(text("SELECT set_config('app.org_id', :org, true)"), {"org": str(org)})
    conn.execute(text("SELECT set_config('app.role', 'owner', true)"))
    try:
        with Session(bind=conn) as session:
            rows = session.scalars(
                select(models_v2.VersionShift).where(models_v2.VersionShift.version_id == version)
            )
            roster = [snapshot_db.to_shift(r) for r in rows]
            snap = snapshot_db.load(session, outlet_id, week, roster, schedule)
            return metrics.as_contract(metrics.compute(snap, roster))
    finally:
        conn.execute(text("RESET ROLE"))
        conn.execute(text("SELECT set_config('app.org_id', '', true)"))


def publish_week(conn: Connection, org_key: str = SPICE, week: date = WEEK) -> None:
    """Seed one published version per outlet through the normal draft -> published path."""
    org = uid("org", org_key)
    for key, _ in OUTLETS:
        schedule = uid("schedule", f"{key}:{week}")
        version_key = f"{key}:{week}:seed"
        version = uid("version", version_key)
        conn.execute(
            insert(Base.metadata.tables["schedules"]),
            {"id": schedule, "org_id": org, "outlet_id": uid("outlet", key), "week_start": week},
        )
        conn.execute(
            insert(Base.metadata.tables["schedule_versions"]),
            {
                "id": version,
                "org_id": org,
                "schedule_id": schedule,
                "version_number": 1,
                "status": "draft",
                "source": "seed",
                "reason": "Initial roster",
                "created_by_user_id": uid("user", "owner"),
                "input_hash": "seed",
            },
        )
        planned = build_roster(week, with_preferred_extras=True, staff=STAFF[key])
        logical, shifts = [], []
        for sh in planned:
            shift_id, logical_id = shift_identity(key, version_key, sh.key)
            t = sh.template
            locked = sh.employee == "ravi" and sh.day.weekday() == 5
            logical.append(
                {"id": logical_id, "org_id": org, "schedule_id": schedule, "created_in_version_id": version}
            )
            shifts.append(
                {
                    "id": shift_id,
                    "org_id": org,
                    "schedule_id": schedule,
                    "version_id": version,
                    "logical_shift_id": logical_id,
                    "outlet_id": uid("outlet", key),
                    "employee_id": uid("employee", sh.employee) if sh.employee else None,
                    "skill_id": SKILL[sh.skill],
                    "start_at": at(sh.day, t.start),
                    "end_at": at(sh.day, t.end),
                    "break_start_at": at(sh.day, t.break_start) if t.break_start is not None else None,
                    "break_minutes": 30 if t.break_start is not None else 0,
                    "locked": locked,
                    "lock_reason": "Locked by manager" if locked else None,
                    "template_id": uid("template", f"{key}:{t.key}"),
                }
            )
        conn.execute(insert(Base.metadata.tables["logical_shifts"]), logical)
        conn.execute(insert(Base.metadata.tables["version_shifts"]), shifts)
        measured = _measure(conn, org, uid("outlet", key), week, schedule, version)
        conn.execute(
            text(
                "UPDATE schedule_versions SET status = 'published', published_at = :at, "
                "approved_by_user_id = :owner, metrics = CAST(:metrics AS jsonb) WHERE id = :v"
            ),
            {
                "at": stamp("2026-10-17T15:14:00"),
                "owner": uid("user", "owner"),
                "v": version,
                "metrics": json.dumps(measured),
            },
        )
        conn.execute(
            text("UPDATE schedules SET current_version_id = :v WHERE id = :s"), {"v": version, "s": schedule}
        )
    # A pending leave request on a day the employee is off at Indiranagar (no conflict).
    day = week + timedelta(days=3)
    working = {sh.employee for sh in build_roster(week, with_preferred_extras=True) if sh.day == day}
    off = next(e for e in STAFF["indiranagar"] if e.key not in working)
    conn.execute(
        insert(Base.metadata.tables["absences"]),
        {
            "id": uid("absence", f"{off.key}:{day}"),
            "org_id": org,
            "employee_id": uid("employee", off.key),
            "start_at": at(day, 0),
            "end_at": at(day, 1440),
            "kind": "leave",
            "status": "requested",
            "reported_by_user_id": uid("user", "staff_ravi") if off.key == "ravi" else None,
            "source": "employee",
        },
    )


def load_org(conn: Connection, org_key: str, *, seed: int = 42) -> dict[str, int]:
    rows = org_rows(org_key, seed=seed)
    reset_org(conn, uid("org", org_key))
    counts: dict[str, int] = {}
    for table in Base.metadata.sorted_tables:
        batch = rows.tables.get(table.name)
        if batch:
            conn.execute(insert(table), batch)
            counts[table.name] = len(batch)
    if org_key == SPICE:
        publish_week(conn)
    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org", choices=[*ORGS, "all"], default="all")
    args = parser.parse_args()
    with admin_engine().begin() as conn:
        for org_key in ORGS if args.org == "all" else (args.org,):
            counts = load_org(conn, org_key)
            print(f"{org_key}: " + ", ".join(f"{t}={n}" for t, n in counts.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
