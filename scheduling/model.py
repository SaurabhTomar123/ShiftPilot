"""Plain, database-free inputs for validation and optimization.

A Snapshot is everything needed to judge one outlet-week roster: the people, their rules, the
demand, and the employees' other live commitments (other outlets and adjacent weeks), so
cross-boundary rest, overlap, travel and weekly caps are checked too (roadmap decision 4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Window:
    weekday: int  # 0 = Monday, outlet-local
    start_minute: int
    end_minute: int  # may exceed 1440 (continues past midnight)
    kind: str  # available | preferred | unavailable


@dataclass(frozen=True)
class Employee:
    id: UUID
    name: str
    home_outlet_id: UUID
    status: str
    skill_ids: frozenset[UUID]
    rate_paise_per_hour: int
    regular_weekly_minutes: int
    max_weekly_minutes: int
    overtime_allowed: bool
    windows: tuple[Window, ...] = ()


@dataclass(frozen=True)
class Outlet:
    id: UUID
    name: str
    timezone: str
    # weekday -> list of (open_minute, close_minute); close may exceed 1440
    operating_hours: dict[int, tuple[tuple[int, int], ...]]

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


@dataclass(frozen=True)
class Absence:
    employee_id: UUID
    start_at: datetime
    end_at: datetime
    status: str  # only "confirmed" invalidates shifts


@dataclass(frozen=True)
class Shift:
    logical_id: UUID
    outlet_id: UUID
    employee_id: UUID | None
    skill_id: UUID
    start_at: datetime
    end_at: datetime
    break_minutes: int = 0
    break_start_at: datetime | None = None
    locked: bool = False

    @property
    def paid_minutes(self) -> int:
        return int((self.end_at - self.start_at).total_seconds() // 60) - self.break_minutes

    def on_break(self, instant: datetime) -> bool:
        return (
            self.break_start_at is not None
            and self.break_start_at <= instant < self.break_start_at + timedelta(minutes=self.break_minutes)
        )


@dataclass(frozen=True)
class Requirement:
    outlet_id: UUID
    skill_id: UUID
    interval_start: datetime
    interval_end: datetime
    minimum: int
    preferred: int


@dataclass(frozen=True)
class Policy:
    min_rest_minutes: int = 600
    grid_minutes: int = 30
    ot_multiplier_bp: int = 20000  # 2.0x; overtime cost reports the premium above base pay


@dataclass(frozen=True)
class Snapshot:
    outlet_id: UUID
    week_start: date  # Monday, outlet-local
    policy: Policy
    outlets: dict[UUID, Outlet]
    employees: dict[UUID, Employee]
    skill_names: dict[UUID, str]
    requirements: tuple[Requirement, ...] = ()
    absences: tuple[Absence, ...] = ()
    travel_minutes: dict[tuple[UUID, UUID], int] = field(default_factory=dict)
    # Live shifts outside the roster being judged (other outlets, adjacent weeks).
    commitments: tuple[Shift, ...] = ()
    # Locked shifts of the base version, by logical id: they must survive unchanged.
    base_locked: dict[UUID, Shift] = field(default_factory=dict)

    @property
    def outlet(self) -> Outlet:
        return self.outlets[self.outlet_id]

    def week_bounds(self) -> tuple[datetime, datetime]:
        d = self.week_start
        start = datetime(d.year, d.month, d.day, tzinfo=self.outlet.tz)
        return start, start + timedelta(days=7)
