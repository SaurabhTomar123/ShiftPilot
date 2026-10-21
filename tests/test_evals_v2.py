"""B6.1: the evaluation suites keep their size, and the language and security cases pass offline.

The scheduling scenarios take a few seconds each, so CI checks they exist; python -m evals.v2 --gate
runs them nightly with the report tied to the commit and configuration hash."""

from __future__ import annotations

from collections import Counter

from evals.v2 import language, scheduling
from language.scripted import ScriptedModel


def test_suites_meet_the_planned_size() -> None:
    sched = Counter(s.suite for s in scheduling.scenarios())
    lang = Counter(c.suite for c in language.cases())
    assert sum(sched.values()) >= 50 and set(sched) == {
        "normal",
        "impossible",
        "overtime",
        "locks",
        "repair",
        "rules_enforced",
        "multi_outlet",
    }
    assert lang["commands"] + lang["ambiguity"] + lang["rule_language"] >= 30 and lang["security"] >= 5


def test_language_and_security_cases_pass_offline() -> None:
    model = ScriptedModel()
    failures = [(c.name, detail) for c in language.cases() for ok, detail in [c.run(model)] if not ok]
    assert failures == []
