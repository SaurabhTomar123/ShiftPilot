from datetime import date, datetime, timedelta
from decimal import Decimal as D

import pytest

from core.clock import IST
from core.money import fmt_inr
from core.payroll import (
    DeductionLine,
    OtRule,
    WorkDay,
    compute_payslip,
    diff_payslips,
    payslip_from_json,
    worked_hours,
)

MON = date(2026, 10, 5)


def days(hours: list[str], rate: str = "100") -> list[WorkDay]:
    return [WorkDay(MON + timedelta(days=i), D(h), D(rate)) for i, h in enumerate(hours)]


def test_regular_week_has_no_overtime() -> None:
    slip = compute_payslip(days(["8"] * 6), [], [])
    assert slip.regular_hours == D("48.00")
    assert slip.ot_hours == 0
    assert slip.base_pay == D("4800.00")
    assert slip.net_pay == D("4800.00")


def test_daily_overtime_above_nine_hours() -> None:
    slip = compute_payslip(days(["11"]), [], [])
    assert (slip.regular_hours, slip.ot_hours) == (D("9.00"), D("2.00"))
    assert slip.ot_pay == D("400.00")  # 2 h x 100 x 2.0


def test_weekly_overtime_taken_from_latest_days() -> None:
    slip = compute_payslip(days(["9"] * 6), [], [])  # 54 h, none above daily threshold
    assert slip.regular_hours == D("48.00")
    assert slip.ot_hours == D("6.00")


def test_mid_period_rate_change_pays_each_day_at_its_rate() -> None:
    work = days(["8", "8"], "100") + [WorkDay(MON + timedelta(days=2), D("8"), D("120"))]
    slip = compute_payslip(work, [], [])
    assert slip.base_pay == D("2560.00")
    assert slip.rates == [D("100"), D("120")]


def test_net_includes_tips_and_deductions() -> None:
    slip = compute_payslip(days(["8"]), [D("150.50")], [DeductionLine("meal", D("200"))])
    assert slip.net_pay == D("750.50")
    assert slip.deductions_by_type == {"meal": D("200.00")}


def test_diff_reconciles_and_explains() -> None:
    prev = compute_payslip(days(["8"] * 6), [D("900")], [])
    curr = compute_payslip(days(["8"] * 4), [D("500")], [DeductionLine("uniform", D("240"))])
    total, changes = diff_payslips(prev, curr)
    assert total == curr.net_pay - prev.net_pay
    assert sum(c.delta for c in changes) == total
    reasons = {c.component: c.reason for c in changes}
    assert "2 fewer shifts" in reasons["base_pay"]
    assert "deduction_uniform" in reasons


def test_json_round_trip() -> None:
    slip = compute_payslip(days(["10", "8"]), [D("100")], [DeductionLine("meal", D("50"))])
    assert payslip_from_json(slip.to_json()) == slip


def test_missing_clock_out_paid_to_scheduled_end() -> None:
    start = datetime(2026, 10, 5, 7, 0, tzinfo=IST)
    hours, missing = worked_hours(start, None, start + timedelta(hours=8))
    assert (hours, missing) == (D("8.00"), True)


@pytest.mark.parametrize(("value", "expected"), [
    (D("1234567.5"), "₹12,34,567.50"), (D("240"), "₹240"), (D("-2824.46"), "-₹2,824.46"),
])
def test_indian_number_format(value: D, expected: str) -> None:
    assert fmt_inr(value) == expected


def test_custom_ot_rule() -> None:
    slip = compute_payslip(days(["10"]), [], [], OtRule(D("8"), D("40"), D("1.5")))
    assert slip.ot_hours == D("2.00")
    assert slip.ot_pay == D("300.00")
