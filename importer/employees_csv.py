"""Employee CSV onboarding (architecture v3 section 19, task B5.4). Pure: no database or HTTP.

The template's columns are fixed (no fuzzy or AI mapping in the MVP):

    name,outlet,skills,hourly_rate,max_weekly_hours,preferred_weekly_hours,
    mon_start,mon_end,tue_start,tue_end,...,sun_start,sun_end

parse() validates every row against the organization's outlets, skills and existing employees and
returns one result per data row with its errors; nothing is written. The caller commits all rows in one
transaction, or none.
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from uuid import UUID

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
COLUMNS = (
    "name",
    "outlet",
    "skills",
    "hourly_rate",
    "max_weekly_hours",
    "preferred_weekly_hours",
    *(f"{d}_{edge}" for d in DAYS for edge in ("start", "end")),
)
MAX_ROWS = 1000
MAX_RATE = Decimal(100_000)
MAX_WEEKLY_HOURS = 80
GRID = 30
EXAMPLE = (
    "Asha Nair,Indiranagar,Grill;Prep,190,48,40,"
    "10:00,22:00,10:00,22:00,,,10:00,22:00,16:00,23:30,16:00,23:30,,"
)
_TIME = re.compile(r"^(\d{1,2}):(\d{2})$")


@dataclass
class Row:
    row_number: int  # 1-based line number in the file, the header being line 1
    name: str = ""
    outlet_id: UUID | None = None
    skill_ids: list[UUID] = field(default_factory=list)
    hourly_rate_paise: int = 0
    max_weekly_minutes: int = 0
    preferred_weekly_minutes: int | None = None
    windows: list[tuple[int, int, int]] = field(default_factory=list)  # (weekday, start, end) minutes
    errors: list[tuple[str, str]] = field(default_factory=list)  # (column, message)

    @property
    def valid(self) -> bool:
        return not self.errors


def _minute(text: str) -> int | None:
    m = _TIME.match(text)
    if not m:
        return None
    hours, minutes = int(m.group(1)), int(m.group(2))
    if minutes >= 60 or hours > 24 or (hours == 24 and minutes):
        return None
    return hours * 60 + minutes


def _hours(text: str) -> int | None:
    """Hours as minutes, on the half-hour."""
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    minutes = value * 60
    if minutes != minutes.to_integral_value() or int(minutes) % GRID:
        return None
    return int(minutes)


def header_errors(header: list[str]) -> list[str]:
    names = [h.strip().lower() for h in header]
    if names == list(COLUMNS):
        return []
    missing = [c for c in COLUMNS if c not in names]
    extra = [h for h in names if h not in COLUMNS]
    problems = []
    if missing:
        problems.append("Missing columns: " + ", ".join(missing) + ".")
    if extra:
        problems.append("Unknown columns: " + ", ".join(extra) + ".")
    if not problems:
        problems.append("Columns must be in the template's order.")
    return problems


def parse(
    text: str,
    *,
    outlets: Mapping[str, UUID],
    skills: Mapping[str, UUID],
    existing: set[tuple[UUID, str]],
) -> tuple[list[str], list[Row]]:
    """(file-level errors, rows). outlets maps lower-case names and slugs to ids; skills maps lower-case
    names to ids; existing holds (outlet id, lower-case name) of current employees."""
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    lines = [line for line in reader if any(cell.strip() for cell in line)]
    if not lines:
        return ["The file is empty. Use the template's header row."], []
    problems = header_errors(lines[0])
    if problems:
        return problems, []
    if len(lines) - 1 > MAX_ROWS:
        return [f"At most {MAX_ROWS} employees per import."], []
    rows: list[Row] = []
    seen: dict[tuple[UUID, str], int] = {}
    for number, cells in enumerate(lines[1:], start=2):
        row = Row(number)
        rows.append(row)
        if len(cells) != len(COLUMNS):
            row.errors.append(("*", f"Expected {len(COLUMNS)} values, found {len(cells)}."))
            continue
        v = dict(zip(COLUMNS, (c.strip() for c in cells), strict=True))
        row.name = v["name"]
        if not row.name or len(row.name) > 120:
            row.errors.append(("name", "Required, at most 120 characters."))
        row.outlet_id = outlets.get(v["outlet"].lower())
        if row.outlet_id is None:
            row.errors.append(("outlet", f"Unknown outlet '{v['outlet']}'."))
        names = [k.strip() for k in v["skills"].split(";") if k.strip()]
        unknown = [k for k in names if k.lower() not in skills]
        if not names:
            row.errors.append(("skills", "At least one role, separated by ';'."))
        elif unknown:
            row.errors.append(("skills", "Unknown roles: " + ", ".join(unknown) + "."))
        row.skill_ids = sorted({skills[k.lower()] for k in names if k.lower() in skills}, key=str)
        try:
            rate = Decimal(v["hourly_rate"])
            if rate < 0 or rate > MAX_RATE or rate != rate.quantize(Decimal("0.01")):
                raise InvalidOperation
            row.hourly_rate_paise = int(rate * 100)
        except InvalidOperation:
            row.errors.append(("hourly_rate", "A rupee amount from 0 to 100000, at most 2 decimals."))
        cap = _hours(v["max_weekly_hours"])
        if cap is None or not 0 < cap <= MAX_WEEKLY_HOURS * 60:
            row.errors.append(
                ("max_weekly_hours", f"Hours from 0.5 to {MAX_WEEKLY_HOURS}, on the half-hour.")
            )
        else:
            row.max_weekly_minutes = cap
        if v["preferred_weekly_hours"]:
            preferred = _hours(v["preferred_weekly_hours"])
            if preferred is None or preferred < 0 or (cap is not None and preferred > cap):
                row.errors.append(
                    ("preferred_weekly_hours", "Hours on the half-hour, at most max_weekly_hours; or empty.")
                )
            else:
                row.preferred_weekly_minutes = preferred
        for weekday, day in enumerate(DAYS):
            a, b = v[f"{day}_start"], v[f"{day}_end"]
            if not a and not b:
                continue  # not available that day
            start, end = _minute(a), _minute(b)
            if start is None or end is None or start % GRID or end % GRID or start >= 1440:
                row.errors.append((f"{day}_start", "Times as HH:MM on the half-hour, or both empty."))
                continue
            if end <= start:
                end += 1440  # overnight, e.g. 18:00-02:00
            if end - start > 1440 or end == start:
                row.errors.append((f"{day}_end", "The window must end after it starts."))
                continue
            row.windows.append((weekday, start, end))
        if row.outlet_id is not None and row.name:
            key = (row.outlet_id, row.name.lower())
            if key in existing:
                row.errors.append(("name", "An employee with this name already works at this outlet."))
            elif key in seen:
                row.errors.append(("name", f"Duplicate of row {seen[key]}."))
            else:
                seen[key] = number
    return [], rows
