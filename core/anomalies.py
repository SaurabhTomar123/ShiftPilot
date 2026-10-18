"""Pure anomaly detectors. Each returns evidence a manager can verify, never a guess."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from core.money import fmt_inr

OT_SPIKE_HOURS = Decimal("12")


@dataclass(frozen=True)
class Anomaly:
    type: str
    severity: str  # low | medium | high
    employee_id: str | None
    day: date | None
    evidence: str
    source_ids: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "severity": self.severity,
            "employee_id": self.employee_id,
            "day": self.day.isoformat() if self.day else None,
            "evidence": self.evidence,
            "source_ids": list(self.source_ids),
        }


@dataclass(frozen=True)
class AttendanceRec:
    id: str
    employee_id: str
    day: date
    hours: Decimal
    clock_out_missing: bool


@dataclass(frozen=True)
class DeductionRec:
    id: str
    employee_id: str
    pay_period_id: str
    type: str
    amount: Decimal


@dataclass(frozen=True)
class TipRec:
    id: str
    day: date
    total: Decimal
    allocated: Decimal


@dataclass(frozen=True)
class RateChangeRec:
    id: str
    employee_id: str
    effective_from: date
    old_rate: Decimal
    new_rate: Decimal


def missing_clock_outs(rows: list[AttendanceRec]) -> list[Anomaly]:
    return [
        Anomaly("missing_clock_out", "medium", r.employee_id, r.day,
                f"No clock-out on {r.day}; paid to scheduled end ({r.hours} h).", (r.id,))
        for r in rows if r.clock_out_missing
    ]


def ot_spikes(rows: list[AttendanceRec], limit: Decimal = OT_SPIKE_HOURS) -> list[Anomaly]:
    return [
        Anomaly("ot_spike", "high", r.employee_id, r.day,
                f"Worked {r.hours} h on {r.day} (limit {limit} h).", (r.id,))
        for r in rows if r.hours > limit
    ]


def duplicate_deductions(rows: list[DeductionRec]) -> list[Anomaly]:
    keyed = Counter((r.employee_id, r.pay_period_id, r.type, r.amount) for r in rows)
    out = []
    for (emp, period, ded_type, amount), count in sorted(keyed.items()):
        if count > 1:
            ids = tuple(r.id for r in rows
                        if (r.employee_id, r.pay_period_id, r.type, r.amount)
                        == (emp, period, ded_type, amount))
            out.append(Anomaly("duplicate_deduction", "high", emp, None,
                               f"{count}x {ded_type} deduction of {fmt_inr(amount)} in the same "
                               "pay period.", ids))
    return out


def tip_mismatches(rows: list[TipRec]) -> list[Anomaly]:
    return [
        Anomaly("tip_mismatch", "high", None, r.day,
                f"Tips collected {fmt_inr(r.total)} but allocated {fmt_inr(r.allocated)} "
                f"(difference {fmt_inr(r.total - r.allocated)}).", (r.id,))
        for r in rows if r.total != r.allocated
    ]


def mid_period_rate_changes(rows: list[RateChangeRec], period_start: date,
                            period_end: date) -> list[Anomaly]:
    return [
        Anomaly("rate_change_mid_period", "low", r.employee_id, r.effective_from,
                f"Hourly rate changed {fmt_inr(r.old_rate)} -> {fmt_inr(r.new_rate)} on "
                f"{r.effective_from}, inside the pay period; pay is split by day.", (r.id,))
        for r in rows if period_start < r.effective_from <= period_end
    ]
