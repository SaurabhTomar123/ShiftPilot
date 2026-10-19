"""Architecture v3 section 31: which metric movements need the manager's acknowledgement."""

from __future__ import annotations

from typing import Any

from scheduling.metrics import material_changes


def m(
    cost: int = 1_000_000, coverage: float | None = 0.9, deficit: int = 0, open_shifts: int = 0
) -> dict[str, Any]:
    return {
        "labour_cost": {"amount_paise": cost, "currency": "INR"},
        "coverage_ratio": coverage,
        "minimum_deficit_minutes": deficit,
        "open_shifts": open_shifts,
    }


def test_small_drift_needs_no_acknowledgement() -> None:
    assert material_changes(m(), m(cost=1_015_000, coverage=0.895)) == []  # +1.5% and -0.5 points


def test_cost_beyond_tolerance_is_material_and_explained() -> None:
    [delta] = material_changes(m(cost=18_000), m(cost=22_000 + 10_000))  # INR 180 -> INR 320
    assert delta["metric"] == "labour_cost" and delta["after"] - delta["before"] == 14_000
    assert delta["message"] == "Cost has risen by INR 140 since this plan was proposed."
    assert material_changes(m(cost=18_000), m(cost=22_000)) == []  # INR 40 is within the INR 100 floor


def test_coverage_shortfall_and_open_shifts() -> None:
    deltas = material_changes(m(), m(coverage=0.85, deficit=30, open_shifts=1))
    assert [d["metric"] for d in deltas] == ["coverage_ratio", "minimum_deficit_minutes", "open_shifts"]
    assert material_changes(m(deficit=30, open_shifts=2), m(deficit=0, open_shifts=1)) == []  # improvements
    assert material_changes(m(coverage=None), m(coverage=0.5)) == []
