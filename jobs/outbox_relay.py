"""Outbox relay (architecture v3 section 40, B6.3): delivers outbox events as in-app notifications.

    python -m jobs.outbox_relay          # serve forever
    python -m jobs.outbox_relay --once   # one batch (tests, cron)

At-least-once processing with duplicate suppression: each event is claimed with SKIP LOCKED, its
recipients get one notification_deliveries row each (unique per event, recipient and channel, so a retry
cannot double-deliver in-app), and the event is marked published in the same transaction. A failing
event is retried with backoff and never blocks the others. A slow channel can never fail the change
that wrote the event, because that transaction committed long before.

Runs as the least-privilege shiftpilot_relay role (RELAY_DATABASE_URL, migration 0016).
"""

from __future__ import annotations

import argparse
import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Connection, Engine, text

from db.session import relay_engine

log = logging.getLogger("shiftpilot.outbox")
BATCH = 50
CHANNEL = "in_app"
MAX_BACKOFF = timedelta(hours=1)

CLAIM = text(
    """SELECT id, org_id, topic, aggregate_type, aggregate_id, payload, attempts
         FROM outbox_events
        WHERE published_at IS NULL AND next_attempt_at <= :now
        ORDER BY next_attempt_at, id
        LIMIT :batch
          FOR UPDATE SKIP LOCKED"""
)
MANAGERS = """SELECT id FROM users
               WHERE org_id = :org AND is_active
                 AND (role = 'owner' OR (role = 'manager' AND outlet_id = :outlet))"""


@dataclass(frozen=True)
class Message:
    user_id: uuid.UUID
    title: str


def _ids(conn: Connection, sql: str, **params: Any) -> list[uuid.UUID]:
    return [r[0] for r in conn.execute(text(sql), params)]


def recipients(conn: Connection, event: Any) -> list[Message]:
    """Who hears about an event, and what they are told. Deterministic text, ASCII."""
    p = event.payload or {}
    if event.topic == "schedule.published":
        week = conn.execute(
            text("SELECT week_start FROM schedules WHERE id = :s"), {"s": p.get("schedule_id")}
        ).scalar()
        staff = _ids(
            conn,
            """SELECT DISTINCT u.id FROM users u JOIN version_shifts s ON s.employee_id = u.employee_id
                WHERE s.version_id = :v AND u.role = 'staff' AND u.is_active""",
            v=p.get("version_id"),
        )
        return [Message(u, f"Your schedule for the week of {week:%d %b} was published.") for u in staff]
    if event.topic == "run.finished":
        run = conn.execute(
            text("SELECT kind, outlet_ids, requested_by_user_id FROM optimization_runs WHERE id = :r"),
            {"r": event.aggregate_id},
        ).first()
        if run is None:
            return []
        ok = p.get("job_state") == "succeeded"
        if run.kind == "repair":
            title = (
                "A repair for an absence is ready to review." if ok else "A repair could not be completed."
            )
            return [
                Message(u, title) for u in _ids(conn, MANAGERS, org=event.org_id, outlet=run.outlet_ids[0])
            ]
        if run.requested_by_user_id is not None:
            title = "Your schedule options are ready." if ok else "Generating schedule options failed."
            return [Message(run.requested_by_user_id, title)]
        return []
    if event.topic == "absence.reported":
        outlet = conn.execute(
            text(
                """SELECT e.outlet_id FROM absences a JOIN employees e ON e.id = a.employee_id
                    WHERE a.id = :a"""
            ),
            {"a": event.aggregate_id},
        ).scalar()
        return [
            Message(u, "An absence was confirmed; a repair is being prepared.")
            for u in _ids(conn, MANAGERS, org=event.org_id, outlet=outlet)
        ]
    if event.topic in ("proposal.ready", "proposal.stale"):
        outlet = conn.execute(
            text("SELECT outlet_id FROM schedules WHERE id = :s"), {"s": p.get("schedule_id")}
        ).scalar()
        title = (
            "A plan is waiting for approval."
            if event.topic == "proposal.ready"
            else "A plan went stale: the schedule changed before it was approved."
        )
        return [Message(u, title) for u in _ids(conn, MANAGERS, org=event.org_id, outlet=outlet)]
    return []  # rule.changed, version.metrics.requested: no in-app audience in the MVP


def _deliver(conn: Connection, event: Any, now: datetime) -> int:
    messages = recipients(conn, event)
    for m in messages:
        conn.execute(
            text(
                """INSERT INTO notification_deliveries
                       (id, org_id, event_id, recipient_user_id, channel, topic, title, payload)
                   VALUES (:id, :org, :event, :user, :channel, :topic, :title, CAST(:payload AS jsonb))
                   ON CONFLICT (event_id, recipient_user_id, channel) DO NOTHING"""
            ),
            {
                "id": uuid.uuid7(),
                "org": event.org_id,
                "event": event.id,
                "user": m.user_id,
                "channel": CHANNEL,
                "topic": event.topic,
                "title": m.title,
                "payload": json.dumps(event.payload or {}, default=str),
            },
        )
    conn.execute(
        text("UPDATE outbox_events SET published_at = :now, last_error = NULL WHERE id = :id"),
        {"now": now, "id": event.id},
    )
    return len(messages)


def relay_once(engine: Engine | None = None, *, now: datetime | None = None) -> dict[str, int]:
    """Deliver one batch. Each event commits or retries on its own (savepoints)."""
    engine = engine or relay_engine()
    counts = {"events": 0, "deliveries": 0, "failed": 0}
    with engine.begin() as conn:
        # The database clock, as the worker uses: events are stamped by it (next_attempt_at defaults to
        # now()), so a host clock running slightly behind would skip events that are already due.
        now = now or conn.execute(text("SELECT now()")).scalar_one()
        for event in conn.execute(CLAIM, {"now": now, "batch": BATCH}).all():
            counts["events"] += 1
            savepoint = conn.begin_nested()
            try:
                counts["deliveries"] += _deliver(conn, event, now)
                savepoint.commit()
            except Exception as exc:  # retry later with backoff; other events go on
                savepoint.rollback()
                counts["failed"] += 1
                delay = min(MAX_BACKOFF, timedelta(seconds=2 ** min(event.attempts + 1, 12)))
                conn.execute(
                    text(
                        """UPDATE outbox_events SET attempts = attempts + 1, next_attempt_at = :next,
                                  last_error = :error WHERE id = :id"""
                    ),
                    {"next": now + delay, "error": f"{type(exc).__name__}: {exc}"[:500], "id": event.id},
                )
                log.warning("outbox event %s failed: %s", event.id, exc)
    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.once:
        print(json.dumps(relay_once()))
        return 0
    while True:
        if not relay_once()["events"]:
            time.sleep(2.0)


if __name__ == "__main__":
    raise SystemExit(main())
