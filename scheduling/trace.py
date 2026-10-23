"""Decision trace (architecture v4 section 18). Pure.

Every candidate carries a structured account of the decision:

    summary   coverage, cost and fairness deltas, overtime, cross-outlet moves, changed commitments;
    changes   the v4 taxonomy per logical shift: KEPT, MOVED_TIME, REASSIGNED, CREATED, REMOVED, UNFILLED;
    why       for changed shifts, the chosen person's facts and each alternative's concrete blocking
              rule, with provenance (rule_id, absence_id) -- or "eligible_not_selected", never an
              invented rejection.

Deltas compare with the base version when there is one; on an empty week with the requested plan, so a
manager sees what choosing "Lowest cost" instead of their plan would trade.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from scheduling import diff, metrics, repair
from scheduling.model import Shift, Snapshot

CLASSES = ("KEPT", "MOVED_TIME", "REASSIGNED", "CREATED", "REMOVED", "UNFILLED")
EXPLAIN_LIMIT = 30  # changed shifts explained per candidate; the rest are counted, not explained


@dataclass(frozen=True)
class Change:
    logical_id: UUID
    change: str  # one of CLASSES (never KEPT: kept shifts are only counted)
    kinds: tuple[str, ...]  # the finer diff kinds (moved, resized, reassigned, ...)
    before_employee_id: UUID | None
    after_employee_id: UUID | None


def classify(c: diff.Change) -> str:
    if c.after is None:
        return "REMOVED"
    if c.after.employee_id is None and (c.before is None or c.before.employee_id is not None):
        return "UNFILLED"
    if c.before is None:
        return "CREATED"
    if "reassigned" in c.kinds:
        return "REASSIGNED"
    if {"moved", "resized"} & set(c.kinds):
        return "MOVED_TIME"
    return "KEPT"  # break, lock or role-only edits keep the commitment


def changes(base: Sequence[Shift], roster: Sequence[Shift]) -> tuple[list[Change], dict[str, int]]:
    """Non-kept changes in time order, and counts for every class (KEPT included)."""
    out = []
    counts: Counter[str] = Counter({k: 0 for k in CLASSES})
    touched = set()
    for c in diff.diff(list(base), list(roster)):
        cls = classify(c)
        counts[cls] += 1
        touched.add(c.logical_id)
        if cls != "KEPT":
            out.append(
                Change(
                    c.logical_id,
                    cls,
                    c.kinds,
                    c.before.employee_id if c.before else None,
                    c.after.employee_id if c.after else None,
                )
            )
    counts["KEPT"] += sum(1 for sh in base if sh.logical_id not in touched)
    return out, dict(counts)


def summary(
    snap: Snapshot,
    roster: Sequence[Shift],
    reference: Sequence[Shift] | None,
    compared_to: str | None,
    counts: dict[str, int],
) -> dict[str, Any]:
    m = metrics.compute(snap, roster)
    ref = metrics.compute(snap, reference) if reference is not None else None
    cross = sum(
        1
        for sh in roster
        if sh.employee_id is not None
        and (e := snap.employees.get(sh.employee_id)) is not None
        and e.home_outlet_id != sh.outlet_id
    )
    fair = (
        round(m.fairness_burden_deviation - ref.fairness_burden_deviation, 2)
        if ref and m.fairness_burden_deviation is not None and ref.fairness_burden_deviation is not None
        else None
    )
    return {
        "compared_to": compared_to if ref else None,
        "cost_delta_paise": (
            m.labour_cost_paise + m.overtime_cost_paise - ref.labour_cost_paise - ref.overtime_cost_paise
            if ref
            else None
        ),
        "preferred_gap_delta_minutes": (
            m.preferred_deficit_minutes - ref.preferred_deficit_minutes if ref else None
        ),
        "fairness_delta": fair,
        "overtime_minutes": m.overtime_minutes,
        "cross_outlet_moves": cross,
        "changed_commitments": sum(counts[k] for k in ("MOVED_TIME", "REASSIGNED", "REMOVED", "UNFILLED")),
    }


def build(
    snap: Snapshot,
    strategy: str,
    base: Sequence[Shift],
    roster: Sequence[Shift],
    reference: Sequence[Shift] | None = None,
    *,
    explain: bool = True,
    exclude: frozenset[UUID] = frozenset(),
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """(trace, trace_changes, explanations) as contract-shaped JSON.

    With a base the deltas compare against it; without one against `reference` (the requested plan),
    or nothing for the requested plan itself. Explanations cover changed shifts against a base only:
    on an empty week every shift is new and the facts belong to the shift, not to a change."""
    found, counts = changes(base, roster)
    compared_to = "base_version" if base else ("requested_plan" if reference is not None else None)
    trace = {
        "strategy": strategy,
        "summary": summary(snap, roster, list(base) if base else reference, compared_to, counts),
        "counts": counts,
        "explained_shifts": 0,
        "explanations_truncated": False,
    }
    rows = [
        {
            "logical_shift_id": str(c.logical_id),
            "change": c.change,
            "kinds": list(c.kinds),
            "before_employee_id": str(c.before_employee_id) if c.before_employee_id else None,
            "after_employee_id": str(c.after_employee_id) if c.after_employee_id else None,
        }
        for c in found
    ]
    explanations: list[dict[str, Any]] = []
    if explain and base:
        wanted = {c.logical_id for c in found if c.change in ("REASSIGNED", "CREATED", "UNFILLED")}
        chosen = [sh for sh in roster if sh.logical_id in wanted][:EXPLAIN_LIMIT]
        explained = repair.explain_shifts(snap, base, roster, chosen, exclude)
        explanations = [repair.explanation_json(e) for e in explained]
        trace["explained_shifts"] = len(explanations)
        trace["explanations_truncated"] = len(wanted) > EXPLAIN_LIMIT
    return trace, rows, explanations
