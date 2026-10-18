"""Deterministic payroll maths. The LLM never calculates pay; it only explains these results.

Pay periods are weekly (Mon-Sun). Overtime is computed per day first (hours above the daily
threshold), then weekly (regular hours above the weekly threshold, taken from the latest days).
Each day is paid at the rate effective on that day, so mid-period rate changes are exact.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from core.money import fmt_inr, inr

HOURS = Decimal("0.01")


@dataclass(frozen=True)
class OtRule:
    daily_threshold_hrs: Decimal = Decimal("9")
    weekly_threshold_hrs: Decimal = Decimal("48")
    multiplier: Decimal = Decimal("2.0")


DEFAULT_OT_RULE = OtRule()


@dataclass(frozen=True)
class WorkDay:
    day: date
    hours: Decimal
    rate: Decimal
    shifts: int = 1


@dataclass(frozen=True)
class DeductionLine:
    type: str
    amount: Decimal
    note: str = ""


@dataclass
class Payslip:
    shifts_worked: int
    regular_hours: Decimal
    ot_hours: Decimal
    base_pay: Decimal
    ot_pay: Decimal
    tips_total: Decimal
    deductions_total: Decimal
    net_pay: Decimal
    rates: list[Decimal]
    deductions_by_type: dict[str, Decimal]
    line_items: list[dict[str, Any]] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        """JSON-safe dict (Decimals as strings) for jsonb storage and tool output."""
        raw = asdict(self)
        return _jsonify(raw)  # type: ignore[no-any-return]


def payslip_from_json(data: dict[str, Any]) -> Payslip:
    """Inverse of Payslip.to_json(), used when tools read stored payslips."""
    dec = {k: Decimal(data[k]) for k in ("regular_hours", "ot_hours", "base_pay", "ot_pay",
                                          "tips_total", "deductions_total", "net_pay")}
    return Payslip(
        shifts_worked=int(data["shifts_worked"]),
        rates=[Decimal(r) for r in data["rates"]],
        deductions_by_type={k: Decimal(v) for k, v in data["deductions_by_type"].items()},
        line_items=[{**li, "amount": Decimal(str(li["amount"]))}
                    for li in data.get("line_items", [])],
        **dec,
    )


def _jsonify(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {k: _jsonify(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonify(v) for v in value]
    return value


def worked_hours(clock_in: datetime, clock_out: datetime | None,
                 scheduled_end: datetime) -> tuple[Decimal, bool]:
    """Hours between clock-in and clock-out. A missing clock-out is paid to the scheduled end
    and flagged so a manager can fix it. Returns (hours, was_missing_clock_out)."""
    end = clock_out or scheduled_end
    minutes = max(0, int((end - clock_in).total_seconds() // 60))
    return (Decimal(minutes) / Decimal(60)).quantize(HOURS), clock_out is None


def compute_payslip(
    work_days: list[WorkDay],
    tips: list[Decimal],
    deductions: list[DeductionLine],
    rule: OtRule | None = None,
) -> Payslip:
    rule = rule or DEFAULT_OT_RULE
    days = sorted(work_days, key=lambda d: d.day)

    # Split each day into regular and daily-OT hours.
    split: list[tuple[WorkDay, Decimal, Decimal]] = []
    for d in days:
        regular = min(d.hours, rule.daily_threshold_hrs)
        split.append((d, regular, d.hours - regular))

    # Weekly OT: regular hours beyond the weekly threshold become OT, latest days first.
    excess = sum((r for _, r, _ in split), Decimal(0)) - rule.weekly_threshold_hrs
    if excess > 0:
        for i in range(len(split) - 1, -1, -1):
            if excess <= 0:
                break
            d, regular, ot = split[i]
            moved = min(regular, excess)
            split[i] = (d, regular - moved, ot + moved)
            excess -= moved

    base_pay = inr(sum((d.rate * r for d, r, _ in split), Decimal(0)))
    ot_pay = inr(sum((d.rate * o * rule.multiplier for d, _, o in split), Decimal(0)))
    regular_hours = sum((r for _, r, _ in split), Decimal(0)).quantize(HOURS)
    ot_hours = sum((o for _, _, o in split), Decimal(0)).quantize(HOURS)
    tips_total = inr(sum(tips, Decimal(0)))

    by_type: dict[str, Decimal] = defaultdict(Decimal)
    for ded in deductions:
        by_type[ded.type] += ded.amount
    deductions_total = inr(sum(by_type.values(), Decimal(0)))

    rates = sorted({d.rate for d in days})
    rate_note = " / ".join(f"{fmt_inr(r)}/h" for r in rates) or "-"
    line_items: list[dict[str, Any]] = [
        {"code": "BASE", "label": "Base pay", "amount": base_pay,
         "detail": f"{regular_hours} h at {rate_note}, {sum(d.shifts for d in days)} shifts"},
        {"code": "OT", "label": "Overtime", "amount": ot_pay,
         "detail": f"{ot_hours} h at {rule.multiplier}x"},
        {"code": "TIPS", "label": "Tips", "amount": tips_total, "detail": f"{len(tips)} days"},
    ]
    for ded in deductions:
        line_items.append({"code": f"DED_{ded.type.upper()}", "label": f"Deduction: {ded.type}",
                           "amount": -inr(ded.amount), "detail": ded.note})

    return Payslip(
        shifts_worked=sum(d.shifts for d in days),
        regular_hours=regular_hours,
        ot_hours=ot_hours,
        base_pay=base_pay,
        ot_pay=ot_pay,
        tips_total=tips_total,
        deductions_total=deductions_total,
        net_pay=inr(base_pay + ot_pay + tips_total - deductions_total),
        rates=rates,
        deductions_by_type={k: inr(v) for k, v in sorted(by_type.items())},
        line_items=line_items,
    )


@dataclass(frozen=True)
class Change:
    component: str
    delta: Decimal
    reason: str


def diff_payslips(previous: Payslip, current: Payslip) -> tuple[Decimal, list[Change]]:
    """Explain net-pay difference component by component. Deltas always sum to the net delta."""
    changes: list[Change] = []

    base_delta = current.base_pay - previous.base_pay
    if base_delta:
        parts = []
        shift_delta = current.shifts_worked - previous.shifts_worked
        if shift_delta:
            word = "fewer" if shift_delta < 0 else "more"
            parts.append(f"{abs(shift_delta)} {word} shifts")
        parts.append(f"{previous.regular_hours} h -> {current.regular_hours} h")
        if previous.rates != current.rates:
            old = ", ".join(fmt_inr(r) for r in previous.rates)
            new = ", ".join(fmt_inr(r) for r in current.rates)
            parts.append(f"rate {old}/h -> {new}/h")
        changes.append(Change("base_pay", base_delta, "; ".join(parts)))

    ot_delta = current.ot_pay - previous.ot_pay
    if ot_delta:
        changes.append(Change("ot_pay", ot_delta,
                              f"overtime {previous.ot_hours} h -> {current.ot_hours} h"))

    tips_delta = current.tips_total - previous.tips_total
    if tips_delta:
        changes.append(Change("tips", tips_delta,
                              f"tips {fmt_inr(previous.tips_total)} -> {fmt_inr(current.tips_total)}"))

    for ded_type in sorted(set(previous.deductions_by_type) | set(current.deductions_by_type)):
        before = previous.deductions_by_type.get(ded_type, Decimal(0))
        after = current.deductions_by_type.get(ded_type, Decimal(0))
        if before != after:
            changes.append(Change(f"deduction_{ded_type}", before - after,
                                  f"{ded_type} deduction {fmt_inr(before)} -> {fmt_inr(after)}"))

    total = current.net_pay - previous.net_pay
    if sum((c.delta for c in changes), Decimal(0)) != total:
        raise ValueError("payslip diff does not reconcile with net pay delta")
    return total, changes
