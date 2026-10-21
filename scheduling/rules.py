"""Scheduling rules and precedence (architecture v3 section 21, tasks B5.2 and A3.12). Pure.

There is no numeric priority. Precedence follows scope, and only through explicit exceptions:

1. Facts beat rules. Availability and absences are facts; a rule never makes someone available.
2. A more specific rule (employee > tag > outlet > organization) wins only when it names the rule it
   overrides (overrides_rule_id). Otherwise two applicable rules of the same type that disagree are a
   conflict, caught when the rule is written (conflicts()), never discovered later as infeasibility.
3. Hard rules never silently override each other.

Supported rule types (MVP; anything else is refused):

    max_shift_end_time   {"latest_end_minute": 0..1440, "weekdays": [0..6]}  no shift ends later
    max_days_per_week    {"days": 1..7}                                       at most N working days
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

RULE_TYPES = ("max_shift_end_time", "max_days_per_week")
SCOPE_LEVELS = ("organization", "outlet", "tag", "employee")
SPECIFICITY = {level: n for n, level in enumerate(SCOPE_LEVELS)}
WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


class RuleError(ValueError):
    """A rule that cannot be accepted: wrong parameters or an unsupported type."""


@dataclass(frozen=True)
class Rule:
    id: UUID
    rule_type: str
    scope_level: str  # organization | outlet | tag | employee
    scope: dict[str, Any]  # {} | {"outlet_id"} | {"tag"} | {"employee_id"}
    parameters: dict[str, Any]
    hard: bool = True
    overrides_rule_id: UUID | None = None
    name: str = ""  # the source text, used in messages


@dataclass(frozen=True)
class Person:
    """What scope resolution needs to know about an employee."""

    id: UUID
    name: str
    home_outlet_id: UUID
    tags: frozenset[str] = field(default_factory=frozenset)


def check(rule: Rule) -> None:
    """Schema validation for one rule; raises RuleError with a field-level message."""
    if rule.rule_type not in RULE_TYPES:
        raise RuleError(f"Unsupported rule type '{rule.rule_type}'. Supported: {', '.join(RULE_TYPES)}.")
    if rule.scope_level not in SCOPE_LEVELS:
        raise RuleError(f"Unknown scope level '{rule.scope_level}'.")
    needs = {"organization": set(), "outlet": {"outlet_id"}, "tag": {"tag"}, "employee": {"employee_id"}}
    if set(rule.scope) != needs[rule.scope_level]:
        raise RuleError(
            f"A {rule.scope_level} rule needs exactly {sorted(needs[rule.scope_level]) or 'no'} scope."
        )
    if not rule.hard:
        raise RuleError("Only hard rules are supported in the MVP.")
    p = rule.parameters
    if rule.rule_type == "max_shift_end_time":
        minute, days = p.get("latest_end_minute"), p.get("weekdays")
        if not isinstance(minute, int) or not 0 < minute <= 1440 or minute % 30:
            raise RuleError("latest_end_minute must be on the half-hour, up to 1440.")
        if (
            not isinstance(days, list)
            or not days
            or any(d not in range(7) for d in days)
            or len(set(days)) != len(days)
        ):
            raise RuleError("weekdays must list distinct days 0 (Monday) to 6 (Sunday).")
        if set(p) != {"latest_end_minute", "weekdays"}:
            raise RuleError("max_shift_end_time takes latest_end_minute and weekdays only.")
    else:
        if set(p) != {"days"} or not isinstance(p["days"], int) or not 1 <= p["days"] <= 7:
            raise RuleError("max_days_per_week takes days from 1 to 7.")


def applies(rule: Rule, person: Person) -> bool:
    if rule.scope_level == "organization":
        return True
    if rule.scope_level == "outlet":
        return str(rule.scope["outlet_id"]) == str(person.home_outlet_id)
    if rule.scope_level == "tag":
        return rule.scope["tag"] in person.tags
    return str(rule.scope["employee_id"]) == str(person.id)


def effective(rules: Iterable[Rule], person: Person) -> list[Rule]:
    """The rules that bind one person after explicit exceptions. An exception replaces the rule it
    names for exactly the people both apply to."""
    mine = [r for r in rules if applies(r, person)]
    overridden = {r.overrides_rule_id for r in mine if r.overrides_rule_id is not None}
    return [r for r in mine if r.id not in overridden]


def describe(rule: Rule) -> str:
    p = rule.parameters
    if rule.rule_type == "max_shift_end_time":
        days = p["weekdays"]
        when = (
            "on weekdays"
            if sorted(days) == [0, 1, 2, 3, 4]
            else "every day"
            if len(days) == 7
            else "on " + ", ".join(WEEKDAY_NAMES[d] for d in sorted(days))
        )
        m = p["latest_end_minute"]
        return f"No shift ends after {m // 60:02d}:{m % 60:02d} {when}"
    return f"At most {p['days']} working days a week"


def _disagree(a: Rule, b: Rule) -> bool:
    if a.rule_type != b.rule_type:
        return False
    if a.rule_type == "max_shift_end_time":
        shared = set(a.parameters["weekdays"]) & set(b.parameters["weekdays"])
        return bool(shared) and a.parameters["latest_end_minute"] != b.parameters["latest_end_minute"]
    return a.parameters != b.parameters


@dataclass(frozen=True)
class Conflict:
    rule_id: UUID
    rule_name: str
    people: tuple[str, ...]  # names of the people both rules apply to
    message: str


def conflicts(new: Rule, active: Iterable[Rule], people: Iterable[Person]) -> list[Conflict]:
    """Write-time conflict analysis: an active rule of the same type that disagrees for someone both
    apply to, and that the new rule does not explicitly override (and that does not override it)."""
    found = []
    staff = list(people)
    for old in active:
        if old.id in (new.overrides_rule_id,) or old.overrides_rule_id == new.id or not _disagree(new, old):
            continue
        both = tuple(sorted(p.name for p in staff if applies(new, p) and applies(old, p)))
        if both:
            who = both[0] if len(both) == 1 else f"{both[0]} and {len(both) - 1} more"
            found.append(
                Conflict(
                    old.id,
                    old.name or describe(old),
                    both,
                    f'This conflicts with "{old.name or describe(old)}". {who} '
                    f"{'is' if len(both) == 1 else 'are'} covered by both.",
                )
            )
    return found


# ---------------------------------------------------------------- enforcement (solver, validator)


def end_allowed(rules: Iterable[Rule], start: datetime, end: datetime, tz: ZoneInfo) -> Rule | None:
    """The max_shift_end_time rule a shift [start, end) breaks, if any. A shift that crosses midnight
    ends after any same-day limit."""
    local_start, local_end = start.astimezone(tz), end.astimezone(tz)
    day = local_start.date()
    end_minute = int((local_end - datetime(day.year, day.month, day.day, tzinfo=tz)).total_seconds() // 60)
    for r in rules:
        if (
            r.rule_type == "max_shift_end_time"
            and local_start.weekday() in r.parameters["weekdays"]
            and end_minute > r.parameters["latest_end_minute"]
        ):
            return r
    return None


def max_days(rules: Iterable[Rule]) -> Rule | None:
    """The tightest max_days_per_week rule."""
    limits = [r for r in rules if r.rule_type == "max_days_per_week"]
    return min(limits, key=lambda r: r.parameters["days"], default=None)


def local_day(instant: datetime, tz: ZoneInfo) -> Any:
    return instant.astimezone(tz).date()
