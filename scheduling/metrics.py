"""Authoritative roster metrics (roadmap decisions 1 and 2).

- coverage_ratio = sum(min(scheduled, preferred) x minutes) / sum(preferred x minutes); None without
  demand. Overstaffing never raises it. Hard-minimum shortfall is reported separately.
- Money is integer paise. Each shift's base cost is paid_minutes x hourly_rate / 60, rounded half up
  per shift. Overtime cost is only the premium above base pay for minutes beyond the regular weekly
  threshold, so it is never double counted. This is estimated roster cost, not payroll.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from scheduling.model import Shift, Snapshot
from scheduling.validator import scheduled


@dataclass(frozen=True)
class Cell:
    skill_id: UUID
    interval_start: datetime
    minimum_required: int
    preferred_required: int
    scheduled: int


@dataclass(frozen=True)
class Metrics:
    coverage_ratio: float | None
    minimum_deficit_minutes: int
    preferred_deficit_minutes: int
    labour_cost_paise: int
    overtime_cost_paise: int
    overtime_minutes: int
    preference_match_ratio: float | None
    open_shifts: int
    assigned_minutes: int
    cells: tuple[Cell, ...]


def _round_div(numerator: int, denominator: int) -> int:
    return (numerator + denominator // 2) // denominator


def compute(snap: Snapshot, roster: Iterable[Shift]) -> Metrics:
    shifts = list(roster)
    assigned = [sh for sh in shifts if sh.employee_id is not None]
    cells, covered, target, min_deficit, pref_deficit = [], 0, 0, 0, 0
    for req in sorted(snap.requirements, key=lambda r: (r.interval_start, str(r.skill_id))):
        if req.outlet_id != snap.outlet_id:
            continue
        on = scheduled(assigned, req.skill_id, req.outlet_id, req.interval_start)
        minutes = int((req.interval_end - req.interval_start).total_seconds() // 60)
        cells.append(Cell(req.skill_id, req.interval_start, req.minimum, req.preferred, on))
        covered += min(on, req.preferred) * minutes
        target += req.preferred * minutes
        min_deficit += max(0, req.minimum - on) * minutes
        pref_deficit += max(0, req.preferred - on) * minutes

    labour = 0
    roster_minutes: dict[UUID, int] = defaultdict(int)
    for sh in assigned:
        emp = snap.employees.get(sh.employee_id)  # type: ignore[arg-type]
        if emp is None:
            continue
        labour += _round_div(sh.paid_minutes * emp.rate_paise_per_hour, 60)
        roster_minutes[emp.id] += sh.paid_minutes

    week_start, week_end = snap.week_bounds()
    overtime_minutes = overtime_cost = 0
    for emp_id, minutes in roster_minutes.items():
        emp = snap.employees[emp_id]
        elsewhere = sum(
            c.paid_minutes
            for c in snap.commitments
            if c.employee_id == emp_id and week_start <= c.start_at < week_end
        )
        over = min(minutes, max(0, minutes + elsewhere - emp.regular_weekly_minutes))
        overtime_minutes += over
        premium_bp = max(0, snap.policy.ot_multiplier_bp - 10000)
        overtime_cost += _round_div(over * emp.rate_paise_per_hour * premium_bp, 60 * 10000)

    with_prefs = [
        sh
        for sh in assigned
        if (e := snap.employees.get(sh.employee_id)) is not None  # type: ignore[arg-type]
        and any(w.kind == "preferred" for w in e.windows)
    ]
    matched = sum(_inside_preferred(snap, sh) for sh in with_prefs)
    return Metrics(
        coverage_ratio=round(covered / target, 4) if target else None,
        minimum_deficit_minutes=min_deficit,
        preferred_deficit_minutes=pref_deficit,
        labour_cost_paise=labour,
        overtime_cost_paise=overtime_cost,
        overtime_minutes=overtime_minutes,
        preference_match_ratio=round(matched / len(with_prefs), 4) if with_prefs else None,
        open_shifts=sum(1 for sh in shifts if sh.employee_id is None),
        assigned_minutes=sum(sh.paid_minutes for sh in assigned),
        cells=tuple(cells),
    )


def _inside_preferred(snap: Snapshot, sh: Shift) -> bool:
    emp = snap.employees[sh.employee_id]  # type: ignore[index]
    local = sh.start_at.astimezone(snap.outlets[sh.outlet_id].tz)
    s = local.hour * 60 + local.minute
    e = s + int((sh.end_at - sh.start_at).total_seconds() // 60)
    return any(
        w.kind == "preferred" and w.weekday == local.weekday() and w.start_minute <= s and e <= w.end_minute
        for w in emp.windows
    )


def as_contract(m: Metrics) -> dict[str, object]:
    """The contract's Metrics shape (api.v2.schemas.Metrics), so workers need no API imports."""
    return {
        "coverage_ratio": m.coverage_ratio,
        "minimum_deficit_minutes": m.minimum_deficit_minutes,
        "preferred_deficit_minutes": m.preferred_deficit_minutes,
        "labour_cost": {"amount_paise": m.labour_cost_paise, "currency": "INR"},
        "overtime_cost": {"amount_paise": m.overtime_cost_paise, "currency": "INR"},
        "overtime_minutes": m.overtime_minutes,
        "preference_match_ratio": m.preference_match_ratio,
        "open_shifts": m.open_shifts,
        "assigned_minutes": m.assigned_minutes,
    }


# ---------------------------------------------------------------- material change (architecture v3 s31)

COST_TOLERANCE_PAISE = 10_000  # INR 100
COST_TOLERANCE_SHARE = 0.02
COVERAGE_TOLERANCE = 0.01


def _rupees(paise: int) -> str:
    return f"INR {abs(paise) // 100:,}"


def material_changes(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    """Deltas between two contract Metrics that a manager must acknowledge before publication.

    Cost moving by more than max(INR 100, 2%), coverage moving by a percentage point, or any new
    minimum-staffing shortfall or open shift. Smaller drift (an unrelated availability edit) passes."""
    out: list[dict[str, Any]] = []
    cost_a = int(before["labour_cost"]["amount_paise"])
    cost_b = int(after["labour_cost"]["amount_paise"])
    if abs(cost_b - cost_a) > max(COST_TOLERANCE_PAISE, COST_TOLERANCE_SHARE * cost_a):
        way = "risen" if cost_b > cost_a else "fallen"
        out.append(
            {
                "metric": "labour_cost",
                "before": cost_a,
                "after": cost_b,
                "message": f"Cost has {way} by {_rupees(cost_b - cost_a)} since this plan was proposed.",
            }
        )
    cov_a, cov_b = before.get("coverage_ratio"), after.get("coverage_ratio")
    if cov_a is not None and cov_b is not None and abs(cov_b - cov_a) >= COVERAGE_TOLERANCE:
        out.append(
            {
                "metric": "coverage_ratio",
                "before": cov_a,
                "after": cov_b,
                "message": f"Coverage moved from {cov_a:.0%} to {cov_b:.0%} since this plan was proposed.",
            }
        )
    for metric, label in (
        ("minimum_deficit_minutes", "Minimum-staffing shortfall"),
        ("open_shifts", "Open shifts"),
    ):
        a, b = int(before[metric]), int(after[metric])
        if b > a:
            out.append(
                {
                    "metric": metric,
                    "before": a,
                    "after": b,
                    "message": f"{label} increased from {a} to {b} since this plan was proposed.",
                }
            )
    return out
