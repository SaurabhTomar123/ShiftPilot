# Retention job (architecture v3 §25)

Run it once a day, for example at 03:30 outlet time, from the same host and image as the worker:

    python -m jobs.retention --dry-run   # counts only; changes nothing
    python -m jobs.retention             # applies; prints the counts as JSON

It runs in a single transaction with the admin connection, across tenants. It is safe to repeat: a second run on the same day finds nothing to do.

| Artifact | Lifetime |
|---|---|
| Unselected candidates | 7 days after their run finished. The run is flagged first, and its view then shows `candidates_expired: true`. |
| Discarded drafts, with their shifts and orphaned logical shifts | 7 days after discard (`schedule_versions.discarded_at`). A draft that a remaining proposal still names, or that another version uses as its base, waits. |
| Failed or cancelled runs | The input snapshot is cleared at the next run. The row goes after 30 days. |
| Expired, rejected, stale or failed proposals | A pending proposal past expiry is recorded as `expired`. `result` (the diff, violations and deltas) is cleared after 7 days, and the row is deleted after 30. |
| Applied (succeeded) runs | The input snapshot is cleared after 30 days. Metrics, config, `input_hash`, solver version and base version ids are kept, and `stats.snapshot_purged` is set. |
| Published and superseded versions, approved proposals, audit log | Kept (MVP). |
| Delivered outbox events | 7 days after delivery. |

The counts in the output name each rule (`candidates_deleted`, `drafts_deleted`, and so on), so a scheduler can alert on an unusual spike. Anonymized evaluation exports, which are needed to keep reproducibility without personal data, are a later task.
