"""Natural-language commands and rules as structured, validated intents (architecture v3 section 33).

AI is a translation layer: text -> model structured output -> Pydantic validation -> entity resolution
-> a deterministic operation shown as a preview, never a direct write. Nothing here touches the
database; api.v2.language does that.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from rapidfuzz import fuzz, process

MATCH = 80  # minimum name score
AMBIGUOUS_GAP = 8  # a runner-up this close makes the match ambiguous


class _Strict(BaseModel):
    model_config = ConfigDict(extra="ignore")


class CommandIntent(_Strict):
    intent: Literal["give_time_off", "report_sick", "generate_week", "unsupported"]
    employee_query: str | None = None
    day: date | None = None
    week_start: date | None = None
    outlet_query: str | None = None


class RuleIntent(_Strict):
    supported: bool
    rule_type: Literal["max_shift_end_time", "max_days_per_week"] | None = None
    scope_level: Literal["organization", "outlet", "tag", "employee"] | None = None
    scope_query: str | None = Field(default=None, description="tag, outlet name or employee name")
    latest_end_minute: int | None = None
    weekdays: list[int] | None = None
    days: int | None = None
    reason: str | None = None


def read(model_output: dict[str, Any], kind: type[_Strict]) -> _Strict | None:
    """Validate untrusted model output; None when it does not fit the schema."""
    try:
        return kind.model_validate(model_output)
    except ValidationError:
        return None


COMMAND_PROMPT = """TASK: command
You translate a restaurant manager's request into JSON. Supported intents:
- give_time_off: an employee is off (leave) on one day. Fields: employee_query, day (YYYY-MM-DD).
- report_sick: an employee is sick on one day. Fields: employee_query, day.
- generate_week: create schedule options for a week. Fields: week_start (the Monday, YYYY-MM-DD),
  outlet_query (outlet name, or null for the manager's own outlet).
- unsupported: anything else.
Use only names that appear in the request; never invent one. Resolve relative days from TODAY.
TODAY: {today} ({weekday})
Answer with one JSON object with keys intent, employee_query, day, week_start, outlet_query."""

RULE_PROMPT = """TASK: rule
You translate a scheduling rule into JSON. Supported rule types:
- max_shift_end_time: no shift ends after a time. latest_end_minute (minutes from midnight, on the
  half-hour, 21:00 = 1260), weekdays (0 = Monday .. 6 = Sunday).
- max_days_per_week: at most N working days a week. days (1-7).
Scope: organization (everyone), outlet (scope_query = outlet name), tag (scope_query = a tag such as
student), employee (scope_query = the person's name). Known tags: {tags}. Known outlets: {outlets}.
If the rule is anything else, answer supported=false with a short reason.
Answer with one JSON object with keys supported, rule_type, scope_level, scope_query,
latest_end_minute, weekdays, days, reason."""


@dataclass(frozen=True)
class Candidate:
    id: UUID
    name: str
    score: float


@dataclass(frozen=True)
class Resolution:
    kind: Literal["one", "many", "none"]
    matches: tuple[Candidate, ...]


def resolve(query: str, people: dict[UUID, list[str]]) -> Resolution:
    """Match a name against people (id -> name and aliases). Never guesses: two close matches ask
    "Which Ravi?" and a weak match asks who was meant."""
    best: dict[UUID, Candidate] = {}
    for person_id, names in people.items():
        for name in names:
            score = max(fuzz.WRatio(query, name), fuzz.token_set_ratio(query, name))
            if person_id not in best or score > best[person_id].score:
                best[person_id] = Candidate(person_id, names[0], score)
    ranked = sorted(best.values(), key=lambda c: (-c.score, c.name))
    strong = [c for c in ranked if c.score >= MATCH]
    if not strong:
        return Resolution("none", tuple(ranked[:3]))
    close = [c for c in strong if strong[0].score - c.score < AMBIGUOUS_GAP]
    return Resolution("one", (strong[0],)) if len(close) == 1 else Resolution("many", tuple(close[:5]))


def best_tag(query: str, tags: set[str]) -> str | None:
    found = process.extractOne(query.lower().rstrip("s"), sorted(tags), scorer=fuzz.ratio, score_cutoff=MATCH)
    return found[0] if found else None
