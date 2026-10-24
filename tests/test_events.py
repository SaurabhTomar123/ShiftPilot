"""A4.8: live progress streams (architecture v4 section 49)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest

from api.v2 import events


def frames(chunks: list[str]) -> list[tuple[str, dict[str, Any]]]:
    out = []
    for chunk in chunks:
        lines = dict(
            line.split(": ", 1) for line in chunk.strip().splitlines() if not line.startswith((":", "retry"))
        )
        if "event" in lines:
            out.append((lines["event"], json.loads(lines["data"])))
    return out


@pytest.fixture(autouse=True)
def fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(events, "POLL_SECONDS", 0.0)


def test_one_event_per_change_then_end_when_finished() -> None:
    states: Iterator[events.Snapshot] = iter(
        [
            ({"job_state": "queued", "poll_after_ms": 500}, False),
            ({"job_state": "queued", "poll_after_ms": 300}, False),  # only the polling hint changed
            ({"job_state": "running"}, False),
            ({"job_state": "succeeded"}, True),
        ]
    )
    first = next(states)
    chunks = list(events.stream("run", lambda: next(states), first))
    assert chunks[0] == f"retry: {events.RETRY_MS}\n\n"
    assert frames(chunks) == [
        ("run", {"job_state": "queued", "poll_after_ms": 500}),
        ("run", {"job_state": "running"}),
        ("run", {"job_state": "succeeded"}),
        ("end", {"reason": "finished"}),
    ]


def test_idle_streams_heartbeat_and_end_for_reconnect(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(events, "HEARTBEAT_SECONDS", 0.0)
    monkeypatch.setattr(events, "MAX_SECONDS", 0.05)
    chunks = list(
        events.stream(
            "version", lambda: ({"current_version_id": "v1"}, False), ({"current_version_id": "v1"}, False)
        )
    )
    assert ": keepalive\n\n" in chunks
    assert frames(chunks) == [("version", {"current_version_id": "v1"}), ("end", {"reason": "reconnect"})]
