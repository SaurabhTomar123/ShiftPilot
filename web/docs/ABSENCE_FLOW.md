# Repair Inbox: absence facts and recovery plans

The selected outlet and week scope the saved-record list. Reporting uses local wall-clock times in the outlet timezone and an exclusive end. Invalid ranges and ambiguous/nonexistent newly entered times fail before a write.

Managers can save a confirmed absence or a request. A separate confirmation step precedes confirm, reject or cancel. `POST /v2/absences` uses a stable key for the same payload; writes are never automatically retried. Status PATCH has no replay promise in this pin.

The successful absence response is shown before repair work. Each returned `repair_run_ids` entry is read and tracked separately. Polling is bounded/cancellable; errors retain the saved record and run ID with a read-only status check. There is no generation POST and no publication during reporting/tracking.

An explicit repair reads the latest published version for the selected week and sends its ID. Returned lock conflicts require individual consent; labels use skill/time when the assignment is available. Only owners see cross-outlet consent. Repairs are not disabled by an active generation run.

The UI displays returned stages and reasons, disruption, validation and employee/alternative facts. It does not infer why a person was not selected. Plan Compare shows the returned alternatives and clearly labelled recorded-baseline deltas. Missing fairness burden stays missing. Candidate detail/selection and proposal approval reuse the existing workflow.

Synthetic preview is intentionally limited to supplied provider facts: the Ravi sick day on 21 October, leave request on 23 October and the repair-summary example. The supplied confirm fixture refers to a different, already confirmed record; it is not substituted for confirming the listed request. Unsupported status writes, dates, owner widening and detailed repair candidates return 501, with no fabricated success. Real API integration uses the declared endpoints directly.

Staff self-service absence UI and durable non-absence repair triggers are separate work. See [v4 alignment and delivery order](ARCHITECTURE_V4_ALIGNMENT.md).
