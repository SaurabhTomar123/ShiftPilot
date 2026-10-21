"""B5.2 / A3.12 (architecture v3 section 21): rule schema, precedence, conflicts and enforcement."""

from __future__ import annotations

import uuid
from collections import Counter
from dataclasses import replace

import pytest

from scheduling import rules, solver, validator
from scheduling.rules import Person, Rule, RuleError
from seed import world
from seed.world_snapshot import build

IND = world.HOME
STUDENT = Person(uuid.uuid4(), "Ravi", IND, frozenset({"student"}))
OTHER = Person(uuid.uuid4(), "Asha", IND)


def rule(
    rule_type: str = "max_shift_end_time",
    level: str = "tag",
    scope: dict[str, object] | None = None,
    overrides: uuid.UUID | None = None,
    name: str = "",
    **params: object,
) -> Rule:
    if not params:
        params = (
            {"latest_end_minute": 1260, "weekdays": [0, 1, 2, 3, 4]}
            if rule_type == "max_shift_end_time"
            else {"days": 5}
        )
    default_scope = {"organization": {}, "outlet": {"outlet_id": str(IND)}, "tag": {"tag": "student"}}
    return Rule(
        uuid.uuid4(),
        rule_type,
        level,
        scope if scope is not None else default_scope.get(level, {}),
        params,
        True,
        overrides,
        name,
    )


def test_schema_validation_refuses_what_it_cannot_enforce() -> None:
    rules.check(rule())
    rules.check(rule("max_days_per_week", "organization"))
    for bad in (
        rule("min_rest_hours"),
        rule(latest_end_minute=1275, weekdays=[0]),
        rule(latest_end_minute=1260, weekdays=[]),
        rule("max_days_per_week", "organization", days=9),
        rule(level="employee", scope={"tag": "student"}),
        replace(rule(), hard=False),
    ):
        with pytest.raises(RuleError):
            rules.check(bad)
    assert rules.describe(rule()) == "No shift ends after 21:00 on weekdays"


def test_more_specific_rules_win_only_through_explicit_exceptions() -> None:
    students = rule(name="Students must finish by 9 PM")
    friday = rule(
        level="employee",
        scope={"employee_id": str(STUDENT.id)},
        overrides=students.id,
        latest_end_minute=1380,
        weekdays=[4],
    )
    assert rules.effective([students, friday], STUDENT) == [friday]
    assert rules.effective([students, friday], OTHER) == []
    assert rules.effective([students], STUDENT) == [students]


def test_conflicts_are_caught_when_a_rule_is_written() -> None:
    students = rule(name="Students must finish by 9 PM")
    later = rule(level="organization", latest_end_minute=1380, weekdays=[4])
    [conflict] = rules.conflicts(later, [students], [STUDENT, OTHER])
    assert conflict.rule_id == students.id and conflict.people == ("Ravi",)
    assert conflict.message == 'This conflicts with "Students must finish by 9 PM". Ravi is covered by both.'
    exception = replace(later, overrides_rule_id=students.id)
    assert rules.conflicts(exception, [students], [STUDENT, OTHER]) == []
    assert rules.conflicts(rule(latest_end_minute=1260, weekdays=[5, 6]), [students], [STUDENT]) == []


def test_the_solver_and_validator_enforce_rules() -> None:
    """Rules bind the people they apply to: the two latest workers must finish by 20:00 and the two
    busiest may work three days. Unruled, all four break these rules; ruled, none does."""
    snap = build()
    tz = snap.outlet.tz
    free = solver.solve(snap, "balanced", time_limit=8.0)[1]
    assert free is not None

    def ends_late(sh: object) -> bool:
        return rules.end_allowed([finish_early], sh.start_at, sh.end_at, tz) is not None  # type: ignore[attr-defined]

    def days(roster: tuple[object, ...]) -> Counter[object]:
        worked = {(sh.employee_id, sh.start_at.astimezone(tz).date()) for sh in roster}  # type: ignore[attr-defined]
        return Counter(e for e, _ in worked)

    finish_early = rule(
        level="organization", latest_end_minute=1200, weekdays=list(range(7)), name="Home by 8 PM"
    )
    three_days = rule("max_days_per_week", "organization", name="Three days a week", days=3)
    late = [e for e, _ in Counter(sh.employee_id for sh in free.roster if ends_late(sh)).most_common(2)]
    busy = [e for e, _ in days(free.roster).most_common(2)]
    assert days(free.roster)[busy[0]] > 3
    bound: dict[uuid.UUID, tuple[Rule, ...]] = {e: (finish_early,) for e in late}  # type: ignore[misc]
    for e in busy:
        bound[e] = (*bound.get(e, ()), three_days)  # type: ignore[arg-type]
    ruled = replace(snap, rules=bound)
    status, cand, _ = solver.solve(ruled, "balanced", time_limit=8.0)
    assert cand is not None, status
    assert not any(ends_late(sh) for sh in cand.roster if sh.employee_id in late)
    assert all(days(cand.roster)[e] <= 3 for e in busy)
    assert validator.validate(ruled, cand.roster).valid
    assert not validator.validate(ruled, free.roster).valid  # the unruled roster breaks them


def test_the_validator_names_the_rule_that_breaks() -> None:
    snap = build()
    roster = solver.solve(snap, "balanced", time_limit=8.0)[1]
    assert roster is not None
    late = next(sh for sh in roster.roster if sh.end_at.astimezone(snap.outlet.tz).hour >= 22)
    students = rule(
        level="organization", latest_end_minute=1260, weekdays=list(range(7)), name="Students finish by 9 PM"
    )
    ruled = replace(snap, rules={late.employee_id: (students,)})  # type: ignore[dict-item]
    found = [v for v in validator.validate(ruled, roster.roster).violations if v.code == "rule"]
    assert found and found[0].severity == "hard" and "Students finish by 9 PM" in found[0].message
    assert found[0].facts["rule_id"] == str(students.id)
