# Repair Inbox: absence facts and recovery plans

The selected outlet and week scope the saved-record list. Reporting uses local wall-clock times in the outlet timezone and an exclusive end. Invalid ranges and ambiguous/nonexistent newly entered times fail before a write.

Managers can save a confirmed absence or a request. A separate confirmation step precedes confirm, reject or cancel. `POST /v2/absences` uses a stable key for the same payload; writes are never automatically retried. Status PATCH has no replay promise in this pin.

The successful absence response is shown before repair work. Each returned `repair_run_ids` entry is read and tracked separately. Polling is bounded/cancellable; errors retain the saved record and run ID with a read-only status check. There is no generation POST and no publication during reporting/tracking.

An explicit repair reads the latest published version for the selected week and sends its ID. Returned lock conflicts require individual consent; labels use skill/time when the assignment is available. Only owners see cross-outlet consent. Repairs are not disabled by an active generation run.

The UI displays returned stages and reasons, disruption, validation and employee/alternative facts. It does not infer why a person was not selected. Plan Compare shows returned alternatives and engine deltas with their declared reference. Historical fairness burden and weekly component points remain separate. Missing legacy metrics stay unreported. Detailed reasoning redacts incremental-cost facts when cost access is absent. Candidate detail/selection and proposal approval reuse the existing workflow.

Synthetic preview is limited to supplied provider facts: the Ravi sick day on 21 October, leave request on 23 October and the repair example. Contract 3.18 adds matching repair detail/select fixtures, now connected through a repair-origin draft and normal proposal approval. The repair candidate identity and published base are preserved. Requested-record status-transition fixtures also exist in this pin, but are not yet wired into the preview gateway. Unsupported status writes, dates and owner widening return explicit errors without fabricated success. Real API integration uses the declared endpoints directly.

See [decision evidence and verification](DECISION_REVIEW_FLOW.md).

Find cover is also available here for a direct replacement without moving other shifts; see [replacement review](REPLACEMENT_FLOW.md). Staff self-service absence UI and durable non-absence repair triggers are separate work. See [v4 alignment and delivery order](ARCHITECTURE_V4_ALIGNMENT.md).
