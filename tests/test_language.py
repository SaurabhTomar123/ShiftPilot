"""B5.1 / v3 sections 33-34: the model adapter's resilience, entity resolution and structured intents."""

from __future__ import annotations

import threading
import uuid
from datetime import date
from typing import Any

import pytest

from language import adapter, parsing
from language.scripted import ScriptedModel

TODAY = date(2026, 10, 21)  # a Wednesday


def test_transient_errors_are_retried_at_most_twice() -> None:
    calls: list[int] = []

    def flaky(system: str, user: str) -> dict[str, Any]:
        calls.append(1)
        raise adapter.Transient("timeout")

    guarded = adapter.Guarded(flaky, sleep=lambda _: None)
    with pytest.raises(adapter.LanguageUnavailable):
        guarded.complete_json("s", "u")
    assert len(calls) == 1 + adapter.MAX_RETRIES

    answers = iter([adapter.Transient("busy"), {"ok": True}])

    def recovers(system: str, user: str) -> dict[str, Any]:
        a = next(answers)
        if isinstance(a, Exception):
            raise a
        return a

    assert adapter.Guarded(recovers, sleep=lambda _: None).complete_json("s", "u") == {"ok": True}


def test_the_breaker_opens_then_lets_one_call_try_after_the_cooldown() -> None:
    now = [0.0]
    breaker = adapter.Breaker(threshold=3, cooldown=60, clock=lambda: now[0])
    calls: list[int] = []

    def down(system: str, user: str) -> dict[str, Any]:
        calls.append(1)
        raise RuntimeError("provider down")  # not transient: no retries

    guarded = adapter.Guarded(down, breaker=breaker, sleep=lambda _: None)
    for _ in range(3):
        with pytest.raises(adapter.LanguageUnavailable):
            guarded.complete_json("s", "u")
    with pytest.raises(adapter.LanguageUnavailable, match="paused"):
        guarded.complete_json("s", "u")
    assert len(calls) == 3  # the open breaker does not call the provider
    now[0] = 61
    with pytest.raises(adapter.LanguageUnavailable):
        guarded.complete_json("s", "u")
    assert len(calls) == 4  # half-open: one trial call, which failed and reopened the breaker


def test_concurrent_calls_are_capped() -> None:
    gate = threading.Event()

    def slow(system: str, user: str) -> dict[str, Any]:
        gate.wait(5)
        return {}

    guarded = adapter.Guarded(slow, max_concurrent=1)
    worker = threading.Thread(target=guarded.complete_json, args=("s", "u"))
    worker.start()
    try:
        with pytest.raises(adapter.LanguageUnavailable, match="Too many"):
            guarded.complete_json("s", "u")
    finally:
        gate.set()
        worker.join()


def test_unconfigured_deployments_report_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    from core import config

    adapter.use(None)
    monkeypatch.setattr(config.settings(), "language_model", None)
    with pytest.raises(adapter.LanguageUnavailable, match="not configured"):
        adapter.current()


def test_names_resolve_without_guessing() -> None:
    ravi_k, ravi_s, asha = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    people = {ravi_k: ["Ravi Kumar", "Ravi K."], ravi_s: ["Ravi Shetty"], asha: ["Asha Nair"]}
    assert parsing.resolve("Asha", people).matches[0].id == asha
    assert parsing.resolve("Ravi Kumar", people).kind == "one"
    which = parsing.resolve("Ravi", people)
    assert which.kind == "many" and {c.id for c in which.matches} == {ravi_k, ravi_s}
    assert parsing.resolve("Zubin", people).kind == "none"


def test_model_output_is_validated_not_trusted() -> None:
    assert parsing.read({"intent": "delete_everything"}, parsing.CommandIntent) is None
    assert parsing.read({"intent": "give_time_off", "day": "not a date"}, parsing.CommandIntent) is None
    ok = parsing.read(
        {"intent": "give_time_off", "employee_query": "Ravi", "day": "2026-10-24"}, parsing.CommandIntent
    )
    assert isinstance(ok, parsing.CommandIntent) and ok.day == date(2026, 10, 24)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Give Ravi Saturday off",
            {"intent": "give_time_off", "employee_query": "Ravi", "day": "2026-10-24"},
        ),
        ("Asha is sick tomorrow", {"intent": "report_sick", "employee_query": "Asha", "day": "2026-10-22"}),
        ("Generate next week", {"intent": "generate_week", "week_start": "2026-10-26", "outlet_query": None}),
        ("Order more tomatoes", {"intent": "unsupported"}),
    ],
)
def test_the_scripted_model_answers_like_a_model(text: str, expected: dict[str, Any]) -> None:
    system = parsing.COMMAND_PROMPT.format(today=TODAY, weekday="Wednesday")
    out = ScriptedModel().complete_json(system, text)
    assert {k: out.get(k) for k in expected} == expected


def test_the_scripted_model_compiles_supported_rules_only() -> None:
    system = parsing.RULE_PROMPT.format(tags="student", outlets="Indiranagar")
    students = ScriptedModel().complete_json(system, "Students cannot work later than 9 PM on weekdays")
    assert students == {
        "supported": True,
        "rule_type": "max_shift_end_time",
        "scope_level": "tag",
        "scope_query": "students",
        "latest_end_minute": 1260,
        "weekdays": [0, 1, 2, 3, 4],
    }
    assert ScriptedModel().complete_json(system, "Nobody may work more than 5 days a week")["days"] == 5
    assert ScriptedModel().complete_json(system, "Pay seniors more on Sundays")["supported"] is False
    assert parsing.best_tag("students", {"student", "senior"}) == "student"
