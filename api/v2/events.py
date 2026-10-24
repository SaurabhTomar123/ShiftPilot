"""Live progress over server-sent events (architecture v4 section 49).

SSE is a delivery convenience, not a source of truth: every stream re-reads durable state from
PostgreSQL (briefly, through the same authorized read functions as the GET endpoints) and sends an event
only when that state changes. A stream ends with an `end` event when its run finishes or after
MAX_SECONDS ("reconnect"); clients then reconnect or fall back to the GET endpoint they already poll.

Authentication stays in the Authorization header (no tokens in URLs), so browsers read these streams
with fetch() rather than EventSource.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections.abc import Callable, Iterator
from datetime import date
from typing import Any

from fastapi.responses import StreamingResponse
from sqlalchemy import select

from api.v2 import forecasts, generation
from api.v2.service import _outlet, week_bounds
from core.auth import Caller
from db.models_v2 import Schedule
from db.session import tenant_session

POLL_SECONDS = 0.5
HEARTBEAT_SECONDS = 15.0
MAX_SECONDS = 120.0
RETRY_MS = 3000
TERMINAL = {"succeeded", "failed", "cancelled"}

Snapshot = tuple[dict[str, Any], bool]  # (event data, finished)


class EventStreamResponse(StreamingResponse):
    media_type = "text/event-stream"


def frame(event: str, data: dict[str, Any], event_id: str | None = None) -> str:
    lines = [f"event: {event}"]
    if event_id:
        lines.append(f"id: {event_id}")
    lines.append("data: " + json.dumps(data, separators=(",", ":"), sort_keys=True))
    return "\n".join(lines) + "\n\n"


def _digest(data: dict[str, Any]) -> str:
    stable = {k: v for k, v in data.items() if k != "poll_after_ms"}
    return hashlib.sha256(json.dumps(stable, sort_keys=True, default=str).encode()).hexdigest()[:16]


def stream(kind: str, read: Callable[[], Snapshot], first: Snapshot) -> Iterator[str]:
    """Emit `kind` events on change, heartbeats while idle, and `end` when finished or capped."""
    yield f"retry: {RETRY_MS}\n\n"
    started = beat = time.monotonic()
    data, finished = first
    last: str | None = None
    while True:
        key = _digest(data)
        if key != last:
            yield frame(kind, data, key)
            last = key
        if finished:
            yield frame("end", {"reason": "finished"})
            return
        now = time.monotonic()
        if now - started >= MAX_SECONDS:
            yield frame("end", {"reason": "reconnect"})
            return
        if now - beat >= HEARTBEAT_SECONDS:
            yield ": keepalive\n\n"
            beat = now
        time.sleep(POLL_SECONDS)
        data, finished = read()


def _respond(kind: str, read: Callable[[], Snapshot]) -> EventStreamResponse:
    first = read()  # authorization and not-found errors surface as normal JSON errors, before streaming
    return EventStreamResponse(
        stream(kind, read, first), headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


def run_events(caller: Caller, run_id: uuid.UUID) -> EventStreamResponse:
    def read() -> Snapshot:
        run = generation.get_run(caller, run_id).model_dump(mode="json")
        return run, run["job_state"] in TERMINAL

    return _respond("run", read)


def forecast_events(caller: Caller, run_id: uuid.UUID) -> EventStreamResponse:
    def read() -> Snapshot:
        run = forecasts.get_run(caller, run_id).model_dump(mode="json")
        return run, run["job_state"] in TERMINAL

    return _respond("forecast", read)


def version_events(caller: Caller, outlet_id: uuid.UUID, week_start: date) -> EventStreamResponse:
    """Schedule-version invalidation: an event whenever the week's published version changes."""

    def read() -> Snapshot:
        with tenant_session(caller) as session:
            outlet = _outlet(session, caller, outlet_id)
            week_bounds(outlet, week_start)
            schedule = session.scalars(
                select(Schedule).where(Schedule.outlet_id == outlet_id, Schedule.week_start == week_start)
            ).first()
            data = {
                "outlet_id": str(outlet_id),
                "week_start": week_start.isoformat(),
                "schedule_id": str(schedule.id) if schedule else None,
                "current_version_id": str(schedule.current_version_id)
                if schedule and schedule.current_version_id
                else None,
            }
        return data, False

    return _respond("version", read)
