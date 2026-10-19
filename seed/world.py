"""The synthetic ShiftPilot world shared by the contract fixtures and the v2 seed.

Deterministic: every ID is a UUIDv5 of a readable key, so the same outlet, skill or employee has the
same ID in contracts/v2 fixtures and in a seeded database. Nothing here touches a database or the
API layer. The roster builder is a simple rule-respecting greedy pass, not the solver.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

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


def availability_windows(e: Emp) -> list[tuple[int, int, int, str]]:
    """(weekday, start_minute, end_minute, kind) recurring windows for one employee."""
    windows: list[tuple[int, int, int, str]] = []
    for d in range(7):
        if d in e.unavailable_days:
            windows.append((d, 0, 1440, "unavailable"))
            continue
        end = e.latest_end if (e.latest_end is not None and d < 5) else CLOSE
        windows.append((d, OPEN, end, "available"))
        if e.preferred:
            windows.append((d, e.preferred[0], e.preferred[1], "preferred"))
    return windows


def shift_identity(outlet_key: str, version_key: str, planned_key: str) -> tuple[uuid.UUID, uuid.UUID]:
    """(version_shift_id, logical_shift_id) for a planned shift, identical in fixtures and seed."""
    logical = planned_key if outlet_key == "indiranagar" else f"{uid('outlet', outlet_key)}:{planned_key}"
    return uid("version_shift", f"{version_key}:{planned_key}"), uid("logical_shift", logical)
