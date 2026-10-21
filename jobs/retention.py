"""Daily retention job (architecture v3 section 25, task A3.10).

    python -m jobs.retention              # apply, print counts
    python -m jobs.retention --dry-run    # count only, change nothing

Every derived artifact has an explicit lifetime:

    unselected candidates            7 days after their run finished
    discarded drafts                 7 days after discard (kept while a proposal still names them)
    failed or cancelled runs         input snapshot cleared at once; the run row 30 days
    expired or rejected proposals    pending past expiry is recorded as expired; result (the full
                                     diff, violations, deltas) cleared after 7 days; the row 30 days.
                                     stale and failed proposals are treated the same way.
    applied runs                     input snapshot cleared after 30 days; metrics, config, input_hash,
                                     solver version and base version ids are kept
    published and superseded         kept (MVP); audit log kept (MVP)
    staged or invalid CSV imports    rows deleted 24 hours after upload; the job row 30 days later
    delivered outbox events          7 days

Runs in one transaction across tenants with the admin connection, like the worker.
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Connection, Engine, text

from db.session import admin_engine

log = logging.getLogger("shiftpilot.retention")

SHORT = timedelta(days=7)
LONG = timedelta(days=30)
EMPTY = "'{}'::jsonb"

STEPS: list[tuple[str, str]] = [
    (
        "proposals_expired",
        """UPDATE schedule_proposals
              SET status = 'expired', decided_at = expires_at, result = '{"outcome": "expired"}'::jsonb
            WHERE status = 'pending' AND expires_at <= :now""",
    ),
    (
        "proposal_results_cleared",
        """UPDATE schedule_proposals SET result = NULL
             WHERE status IN ('rejected', 'expired', 'stale', 'failed') AND result IS NOT NULL
               AND decided_at < :short""",
    ),
    (
        "proposals_deleted",
        """DELETE FROM schedule_proposals
            WHERE status IN ('rejected', 'expired', 'stale', 'failed') AND decided_at < :long""",
    ),
    (
        # Recorded on the run first, so its view says the options expired instead of looking broken.
        "runs_marked_expired",
        """UPDATE optimization_runs r
              SET stats = coalesce(r.stats, '{}'::jsonb) || '{"candidates_purged": true}'::jsonb
            WHERE r.finished_at < :short AND NOT coalesce((r.stats->>'candidates_purged')::bool, false)
              AND EXISTS (SELECT 1 FROM optimization_candidates c
                           WHERE c.run_id = r.id AND c.materialized_version_id IS NULL
                             AND NOT EXISTS (SELECT 1 FROM schedule_proposals p
                                              WHERE p.candidate_id = c.id))""",
    ),
    (
        "candidates_deleted",
        """DELETE FROM optimization_candidates c
            USING optimization_runs r
            WHERE r.id = c.run_id AND c.materialized_version_id IS NULL AND r.finished_at < :short
              AND NOT EXISTS (SELECT 1 FROM schedule_proposals p WHERE p.candidate_id = c.id)""",
    ),
    (
        # Discarded drafts that are old enough, not named by a remaining proposal and nobody's base.
        "drafts_purgeable",
        """CREATE TEMP TABLE purge_versions ON COMMIT DROP AS
           SELECT v.id, v.schedule_id FROM schedule_versions v
            WHERE v.status = 'discarded' AND v.discarded_at < :short
              AND NOT EXISTS (SELECT 1 FROM schedule_proposals p WHERE v.id = ANY(p.draft_version_ids))
              AND NOT EXISTS (SELECT 1 FROM schedule_versions b WHERE b.base_version_id = v.id)""",
    ),
    (
        "candidates_unlinked",
        """UPDATE optimization_candidates SET materialized_version_id = NULL
            WHERE materialized_version_id IN (SELECT id FROM purge_versions)""",
    ),
    (
        "draft_shifts_deleted",
        "DELETE FROM version_shifts WHERE version_id IN (SELECT id FROM purge_versions)",
    ),
    ("drafts_deleted", "DELETE FROM schedule_versions WHERE id IN (SELECT id FROM purge_versions)"),
    (
        "logical_shifts_deleted",
        """DELETE FROM logical_shifts l
            WHERE l.schedule_id IN (SELECT schedule_id FROM purge_versions)
              AND NOT EXISTS (SELECT 1 FROM version_shifts s WHERE s.logical_shift_id = l.id)""",
    ),
    (
        "failed_snapshots_cleared",
        f"""UPDATE optimization_runs SET input_snapshot = {EMPTY},
                   stats = coalesce(stats, '{{}}'::jsonb) || '{{"snapshot_purged": true}}'::jsonb
             WHERE job_state IN ('failed', 'cancelled') AND input_snapshot <> {EMPTY}""",
    ),
    (
        "failed_runs_deleted",
        """DELETE FROM optimization_runs r
            WHERE r.job_state IN ('failed', 'cancelled') AND r.finished_at < :long
              AND NOT EXISTS (SELECT 1 FROM optimization_candidates c WHERE c.run_id = r.id)
              AND NOT EXISTS (SELECT 1 FROM schedule_versions v WHERE v.optimization_run_id = r.id)""",
    ),
    (
        "applied_snapshots_cleared",
        f"""UPDATE optimization_runs SET input_snapshot = {EMPTY},
                   stats = coalesce(stats, '{{}}'::jsonb) || '{{"snapshot_purged": true}}'::jsonb
             WHERE job_state = 'succeeded' AND finished_at < :long AND input_snapshot <> {EMPTY}""",
    ),
    (
        "imports_expired",
        """UPDATE import_jobs SET status = 'expired'
            WHERE status IN ('staged', 'invalid') AND expires_at <= :now""",
    ),
    (
        "import_rows_deleted",
        """DELETE FROM import_rows r USING import_jobs j
            WHERE j.id = r.job_id AND j.status = 'expired'""",
    ),
    (
        "imports_deleted",
        "DELETE FROM import_jobs WHERE status = 'expired' AND expires_at < :long",
    ),
    (
        "outbox_deleted",
        "DELETE FROM outbox_events WHERE published_at IS NOT NULL AND published_at < :short",
    ),
]


def _apply(conn: Connection, now: datetime) -> dict[str, int]:
    params = {"now": now, "short": now - SHORT, "long": now - LONG}
    counts: dict[str, int] = {}
    for name, sql in STEPS:
        result = conn.execute(text(sql), params)
        if name == "drafts_purgeable":
            counts[name] = int(conn.execute(text("SELECT count(*) FROM purge_versions")).scalar_one())
        else:
            counts[name] = int(result.rowcount)
    return counts


def run(
    engine: Engine | None = None, *, now: datetime | None = None, dry_run: bool = False
) -> dict[str, Any]:
    """Apply (or, with dry_run, only count) every retention rule in one transaction."""
    engine = engine or admin_engine()
    now = now or datetime.now(UTC)
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            counts = _apply(conn, now)
        except Exception:
            tx.rollback()
            raise
        if dry_run:
            tx.rollback()
        else:
            tx.commit()
    report = {"at": now.isoformat(), "dry_run": dry_run, **counts}
    log.info("retention %s", json.dumps(report))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="count what would go; change nothing")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(json.dumps(run(dry_run=args.dry_run), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
