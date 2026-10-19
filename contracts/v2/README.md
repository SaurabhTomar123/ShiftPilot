# contracts/v2: scheduling API contract (P1–P2)

Provider: Claude (backend). Consumer: Codex (web). Version: see `fixtures/index.json` → `contract_version`.

**Generated files. Do not edit by hand.** The source is `api/v2/schemas.py` and `api/v2/routes.py`. Rebuild with `python -m api.v2.contract_build`. `tests/test_contracts_v2.py` fails if these files are out of date.

## Files

- `openapi.json`: OpenAPI 3.1 for every P1–P2 endpoint, including all error responses. Suitable for client generation, e.g. `openapi-typescript`. Generated clients live under `web/` and belong to Codex.
- `fixtures/index.json`: every fixture, with its operation, status and response schema name.
- `fixtures/<name>.json`: `{name, operation_id, method, path, persona, request, response: {status, schema, body}}`. Each body is validated against its schema at build time and in tests.

## Synthetic dataset

- Org "Spice Route Kitchens" with outlets Indiranagar, Koramangala and HSR Layout, all in `Asia/Kolkata`.
- Five skills: Grill, Prep, Server, Cashier, Barista.
- 13 Indiranagar employees. Ravi Kumar has his Saturday shift locked. Rohit Verma is a student who can't work past 21:00 on weekdays.
- Personas: `owner`, `manager_indiranagar` and `staff_ravi`.
- Week of 19 Oct 2026: published version 3, 60 shifts, 0 hard violations.
- Week of 26 Oct 2026: empty, used for the generate and run fixtures.

IDs are stable UUIDv5 values, so the same entity has the same ID in every fixture.

The roster in the fixtures is built by a simple rule-respecting script, not the real solver. Its metrics (coverage, cost, preferred deficits) are computed from its shifts, so they agree with each other within a fixture. Real values will differ.

## What changed in 3.4.0-p4 (live): profiles and hours-preference alignment

This change is additive (architecture v3 §9).

- **`Metrics.hours_preference_deviation_minutes`:** the sum, over employees with a preferred weekly total, of |worked − preferred| minutes. Lower is better. It is `null` when nobody states a preference, and in metrics stored before 3.4. Label it "hours-preference alignment". It is **not** a fairness measure.
- **Strategies now use v3's weights.** The four names are unchanged. Balanced trades less cost for coverage than before. When regenerating over a published week, assignments that stay the same keep their `logical_shift_id`, so candidate diffs show genuine changes.

## What changed in 3.3.0-p4 (live): answers to the 3.1 consumer review

This change is additive.

- **`listProposals` `GET /v2/proposals?schedule_id=…&status=pending`:** a week's proposals, newest first, at most 100. Repeat `status` to filter by several statuses. Use it to find the pending proposal again after a reload. Fixture: `proposals.list.pending`.
- **Expiry is visible:** a pending proposal past `expires_at` now reads as `expired` in `getProposal` and `listProposals`, not only when someone tries to approve it.
- **Second candidate's fixtures:** `candidate.detail.lowest_cost` and `candidate.select.lowest_cost` cover candidate 2 of `run.succeeded`.
- **Fixture story fixed:** `proposal.approve.acknowledged` now publishes `recorded_metrics` with the moved cost the manager accepted, which matches `proposal.approve.changed`. Publication stores the metrics measured at publication.

## What changed in 3.2.0-p4 (live): repair widening

This change is additive (architecture v3 §12).

- **`OptimizationRun.repair_stages`:** repair runs record each widening stage in the order tried. The stages are `same_day` (the affected days from the absence onward, home staff, no overtime), `adjacent_shifts` (plus the day either side), `other_outlets` (plus other outlets' staff) and `overtime`. Each stage has a `result`: `selected`, `insufficient` (it couldn't keep minimum staffing, so the repair widened), `no_plan` or `skipped` (with a `reason` of `not_authorized` or `same_scope`). It also reports `free_shifts`, `pool` and `minimum_shortfall_minutes`. Use these to explain why a wider change was needed. Fixture: `run.repair.widened`.
- **`RepairRequest.allow_cross_outlet`:** owner only. Managers get `403` (fixture `repair.cross_outlet.manager`). Automatic repairs never borrow staff from other outlets.
- **Repairs also fix shifts that current facts already break,** such as an earlier absence nobody has repaired yet, so every candidate is publishable. If such a shift is locked, the run fails with `409`-style `error.code: conflict` and `details.locked_logical_shift_ids`, the same as a locked affected shift.
- **Fix:** generation now respects confirmed absences of employees who are not yet on the roster, which matters for a fresh week. Previously only people already rostered had their absences loaded.

## What changed in 3.1.0-p4 (live): stored version metrics

This change is additive. Every version summary, including history items and publish results, now has **`recorded_metrics`**. The figures are stored when a draft is created, selected, restored or edited, and recomputed against current facts at publication. After that they are frozen with the version, so history can show what each version cost and covered when it went live without recomputing anything. `ScheduleVersion.metrics` is still evaluated against current facts, so the two can differ for an old version. `recorded_metrics` is `null` only for versions saved before 3.1 (architecture v3 §22).

## Contract 3.0 (architecture v3): breaking changes

`ShiftPilot System Architecture v3` is the governing design. Contract 3.0 changes three shapes the UI depends on.

| Change | Status |
|---|---|
| **Lightweight candidates** (§23) | **Live in 3.0.0-p4.** |
| **Versions served with `Cache-Control: private, no-cache`** (§36) | **Live in 3.0.0-p4.** |
| **Proposals with four publication outcomes** (§31): Published, Stale, Invalid, and Changed (needs acknowledgement) | **Live in 3.0.0-p4.** |

### Lightweight candidates (live)

A candidate is no longer a version. Runs write **no** `schedule_versions`; a manager's selection does:

`candidate --select--> draft --edit (optional)--> publish`

| Operation | What it does | Fixture |
|---|---|---|
| `getOptimizationRun` | `Candidate.draft_version_id` is **removed**. `materialized_version_id` is `null` until the candidate is selected, then it holds the draft it became. | `run.succeeded` |
| `getOptimizationCandidate` `GET /v2/optimization-candidates/{id}` | Returns the candidate with `base_version_id` and its `diff` against that base: `added` and `changed` hold `CandidateShift`s (no row `id` yet), `removed` holds logical shift ids. For generation without a base, every shift is `added`. | `candidate.detail` |
| `selectOptimizationCandidate` `POST /v2/optimization-candidates/{id}/select` | `201` with the materialized draft (`source` `generate` or `repair`, `optimization_run_id` set). Its `base_version_id` is the **run's** base, so publishing after someone else published returns `stale_version`. Selecting again returns the same draft while it is still a draft. Needs `Idempotency-Key` and the `publish` capability. | `candidate.select` |

To preview a candidate, render `diff` over the base version, or select it and use the draft. Logical identity is kept: shifts a repair reassigns appear in `changed` with their existing `logical_shift_id`.

### Proposals and publication outcomes (live)

`candidate --select--> draft --edit (optional)--> proposal --approve--> published version`

| Operation | What it does | Fixture |
|---|---|---|
| `createProposal` `POST /v2/proposals` | Body `{draft_version_id, expected_revision}`. Records the draft revision and its `metrics_at_proposal` against current facts; that is what the manager agrees to. `409 stale_version` if the draft revision moved, `422 validation_failed` if it has hard violations. Expires after 24 hours. Needs `Idempotency-Key`. | `proposal.create` |
| `getProposal` `GET /v2/proposals/{id}` | The proposal and its `status`: `pending`, `approved`, `rejected`, `expired`, `stale` or `failed`. | `proposal.get` |
| `approveProposal` `POST /v2/proposals/{id}/approve` | The publication transaction. **Always `200` with an `outcome`** (below). Body `{acknowledge_changes}`. Needs `Idempotency-Key`; a double click publishes once. `409 conflict` only if the proposal is no longer pending (`details.status`) or has expired. | `proposal.approve.*` |
| `rejectProposal` `POST /v2/proposals/{id}/reject` | Marks it `rejected`. Repeating it is harmless. | `proposal.reject` |

| `outcome` | Proposal status | Meaning | What the UI shows |
|---|---|---|---|
| `published` | `approved` | Base unchanged, plan valid, metrics unchanged or acknowledged. `published` and `superseded_version_id` are set. | The new version |
| `stale` | `stale` | Someone published first (`current_version_id`), or the draft was edited after it was proposed. | `message`, then re-run or re-propose against the latest version |
| `invalid` | `failed` | A current fact breaks the plan, for example a new confirmed absence. `violations` lists them. | "This recommendation is no longer valid" with the reason; offer a repair |
| `changed` | still `pending` | Valid, but metrics moved materially since the proposal. `deltas` carry `before`, `after` and a ready-to-show `message`. | The deltas; **Approve again** sends `acknowledge_changes: true` |

Material means labour cost moved by more than max(INR 100, 2%), coverage moved by at least one percentage point, or minimum-staffing shortfall or open shifts increased. Smaller drift, such as an unrelated availability edit, does not block publication.

`publishVersion` stays available for a manager's own manual draft (stale `409`, invalid `422`). Use proposals for optimizer and repair results.

### Version caching (live)

`getScheduleVersion` always sends `Cache-Control: private, no-cache`. Shift content never changes, but status does (published becomes superseded). The `ETag` is now `"{id}:{status}:{revision}"`, so it changes on supersession and on every applied draft edit. Send it back as `If-None-Match` to get `304`.

## What changed in 2.4.0-p4 (live): absences and repair

| Operation | What it does | Fixture |
|---|---|---|
| `reportAbsence` `POST /v2/absences` | Records the absence as a fact first. A **confirmed** absence then enqueues a repair run per affected schedule (`repair_run_ids`). Locked affected shifts are listed in `lock_conflicts` and get no automatic repair. Staff may only send `requested` absences for themselves. | `absence.report`, `.requested` |
| `listAbsences` `GET /v2/absences?outlet_id&from&to` | Lists absences, including `rejected` and `cancelled`. | `absences.list` |
| `updateAbsence` `PATCH /v2/absences/{id}` | Managers confirm, reject or cancel. Confirming enqueues repairs like `reportAbsence`. | `absence.update.confirm` |
| `repairSchedule` `POST /v2/outlets/{id}/schedules/{week}/repair` | Explicit repair, typically after authorizing locked shifts (`unlock_logical_shift_ids`). Without authorization it returns `409 conflict` with `details.locked_logical_shift_ids`. An active repair for the same absence is returned unchanged. | `repair.accepted`, `.locked` |

Repair runs follow v3 admission:
- They have `kind: repair` and `absence_id`, and are claimed **before** batch work. They are **never blocked by an active generate run**, and `poll_after_ms` is 300.
- Candidates use the repair profiles `least_disruption`, `lowest_cost` and `best_coverage`.
- Each candidate adds `disruption` (`changed_shifts`, `added_shifts`, `cross_outlet_moves`, `open_shifts`) and `explanations`. Per changed shift, these give the chosen person's facts and the alternatives, each either `rejected` with its blocking rule or `eligible_not_selected`, never an inferred reason.
- A repair that cannot keep minimum staffing is reported as `INFEASIBLE` with shortages, not offered as a candidate.

## What changed in 2.3.0-p3 (live)

Additive. Everything from 2.2 is unchanged except one new field: **every version summary now has `revision`** (fixed at 1 for published and superseded versions; bumped by each applied draft edit).

| Operation | What it does | Fixture |
|---|---|---|
| `createDraft` `POST /v2/outlets/{id}/schedules/{week}/drafts` | Creates a new draft copied from the published version, or from `copy_from_version_id`. Stale `base_version_id` returns 409. Needs `Idempotency-Key`. | `draft.create` |
| `previewEdits` `POST /v2/schedule-versions/{id}/edits/preview` | Shows what the draft would become: `shifts`, typed `changes`, authoritative `metrics` and `validation`. **Writes nothing.** Use it for drag, resize and keyboard previews. | `edits.preview` |
| `applyEdits` `POST /v2/schedule-versions/{id}/edits` | Applies edits to a **draft** and bumps `revision`. A stale `expected_revision` returns `409 stale_version` (`details.current_revision`); editing a non-draft returns `409 conflict`. Rule-breaking edits are applied and reported in `validation`. | `edits.apply`, `.stale`, `.not_draft` |
| `publishVersion` `POST /v2/schedule-versions/{id}/publish` | Publishes the draft and supersedes the current version in one atomic step. A moved base or revision returns `409 stale_version`. **Hard violations against current facts return `422 validation_failed` with `details.violations`.** Needs `Idempotency-Key`. | `publish`, `.blocked`, `.stale_base` |
| `discardDraft` `POST /v2/schedule-versions/{id}/discard` | Marks a draft `discarded`. | `draft.discard` |
| `listVersions` `GET /v2/schedules/{schedule_id}/versions` | History, newest first, drafts included. | `versions.list` |
| `compareVersions` `GET /v2/schedule-versions/{id}/compare?with={other}` | Changes from `with` to `id`, keyed on `logical_shift_id`, plus metrics on both sides. | `versions.compare` |
| `restoreVersion` `POST /v2/schedule-versions/{id}/restore` | Creates a **new draft** (`source: restore`) with that version's shifts, validated against current facts. A restored shift for someone now absent shows as a hard violation and is never revived silently. History is never rewritten. | `versions.restore` |

Edits are a discriminated union on `op`:
- `add`: a full shift, optionally open (`employee_id: null`).
- `update`: move, resize, reassign or change role. Omitted fields are unchanged, and moving the start shifts the break with it.
- `remove`.
- `lock` / `unlock`.

`ShiftChange.kinds` uses `added`, `removed`, `reassigned`, `moved`, `resized`, `role_changed`, `lock_changed` and `break_changed`.

The fixture story: draft v4 copies published v3. The preview reassigns a Tuesday Grill shift to Ravi, who is unavailable on Tuesdays, which gives a hard `unavailable` violation. The apply locks Monday's opening Grill shift (revision 2). Then publish; then restore v2 as draft v5.

These eight operations are live (B3.1–B3.3). Publication runs in one transaction: it locks the schedule, takes advisory locks per rostered employee, re-checks the base and revision, and re-validates against the live organization-wide roster. Integration tests cover idempotent replay, stale races, 422 blocking (including a restored shift for an employee who is now absent), and audit plus outbox rows.

## What changed in 2.2.0-p1p2

This release answers the follow-ups in `web/docs/CONTRACT_REVIEW.md` and adds B0.4 from architecture revision 2. It only adds things; nothing from 2.1 was removed or renamed, and every 2.1 fixture keeps its IDs.

| Change | What the UI should do |
|---|---|
| New error code `409 run_in_progress` on generate, with `details.run_id` (fixture `generate.run_in_progress`) | **Attach to that run and poll it.** Do not show an error. This happens when someone else, or another tab, already started a run for this week. |
| `Retry-After` header (seconds) on `429` (fixture `generate.rate_limited`) | Wait at least that long before allowing a retry. |
| `ETag` on `getScheduleWeek`, and `ETag` plus `Cache-Control` on `getScheduleVersion`. `If-None-Match` returns `304` with no body (fixtures `*.not_modified`). | Since 3.0 every version is `no-cache` (status is mutable); revalidate with its `ETag`. Revalidate the week with `If-None-Match`; a changed week `ETag` means a new publication. |
| `schedule_version.draft.lowest_cost` | The full draft of `run.succeeded`'s second candidate. |
| `schedule_week.owner.koramangala` / `.hsr`, `employees.list.owner.*` | Owner rosters for the other two outlets, each with 13 employees and its own published week. |
| `MyWeek.skills` | Skill names for the skill IDs in the employee's shifts. |
| `EmployeeUpdate`: omitting a field means "no change". Explicit `null` is `422`, except `preferred_weekly_minutes`, where `null` clears it (fixture `employees.update.null_field`). | Keep omitting untouched fields. Send `null` only to clear preferred hours. |
| Contract files are now ASCII-only, with non-ASCII escaped as `\uXXXX` in JSON | Any JSON parser decodes them correctly. The earlier "mojibake" came from reading UTF-8 with the Windows ANSI codepage (for example, PowerShell 5.1 `Get-Content` without `-Encoding UTF8`); the bytes were valid. |

Fixture files may now include `response.headers`, and `response.schema`/`response.body` are `null` for 304 responses.

## Rules the UI can rely on

- **Session transport**: every call except `POST /v2/session/demo` sends `Authorization: Bearer <access_token>`.
  - In the public synthetic demo, the UI gets the token from `POST /v2/session/demo {persona}`. That call returns the token, its expiry and `me`.
  - Private deployments return 403 there and use real sign-in, which is not in this contract yet.
  - Keep the token in memory. On a 401, return to persona selection.
  - Never put admin credentials or database URLs in frontend environment variables.
- **Capabilities**: `me.capabilities` says which controls to show, for example `publish` or `view_costs`. Hiding a control is not authorization; the server re-checks every action.
- **Roster rows**: `ScheduleWeek.employees` lists the rows to draw. A row with no shift on a day means the employee is off that day. An open shift (`employee_id: null`) is an unfilled requirement. `absences` marks leave and sickness, and only `confirmed` absences invalidate an overlapping shift.
- **Trace IDs**: `error.trace_id`, when present, should be shown in "report a problem" details.
- **Errors**: always `{"error": {code, message, retryable, details}}`, including 422. `message` is safe to display. Branch on `code`, never on the message text.
- **Concurrency**:
  - Writes carry `base_revision`, `base_demand_revision` or `base_version_id`. A stale value returns `409 stale_version`, with the current value in `details`.
  - POSTs carry an `Idempotency-Key` header. Replaying a key returns the original result. Reusing a key with a different body returns `409 idempotency_conflict`.
- **Generation is asynchronous**: `POST …/generate` → `202` with a run in `queued`. Poll `GET /v2/optimization-runs/{id}`, waiting `poll_after_ms` between calls, until `poll_after_ms` is null. The schema enforces these combinations:

  | `job_state` | `solver_status` | Meaning / what the UI shows |
  |---|---|---|
  | `succeeded` | `OPTIMAL` | Candidates, each with `proven_optimal: true` |
  | `succeeded` | `FEASIBLE` | Valid candidates, but the time limit stopped the search before optimality was proven |
  | `succeeded` | `INFEASIBLE` | `infeasibility.shortages` and no candidates |
  | `succeeded` | `UNKNOWN` | No solution found in time. This does **not** mean the roster is impossible; say so |
  | `failed` | (any) | `error` |
  
- A candidate never has hard violations. Its diff is `GET /v2/optimization-candidates/{id}`; selecting it materializes a draft (contract 3.0).
- **Coverage**: `coverage_ratio` measures cover against **preferred** staffing and can't be inflated by overstaffing. It is `null` when there is no demand. Hard-minimum shortfall is reported separately as `minimum_deficit_minutes`.
- **Time and money**:
  - Instants are ISO 8601 with offset. Display them in the outlet's `timezone`.
  - Recurring times are minutes from local midnight, and Monday is weekday 0.
  - Money is integer paise (`amount_paise`). Format it for display only, and treat the server's numbers as authoritative.
- **Shift identity**: diff versions on `logical_shift_id`. `id` changes with every version.

## Status

**Every declared operation is live.** Nothing returns `501` any more.

- **Data and schedule reads (B1.2):** `validation` and `metrics` come from the independent validator, evaluated against current live facts. A roster published before a confirmed absence shows that absence as a hard violation. `ETag`, `If-None-Match`/304 and `Cache-Control` work as described in 2.2, and authorization always runs first. Coverage cells list only intervals with demand.
- **Generation (B2.2/B2.3):**
  - `generateSchedule` queues a run; a worker process solves it.
  - `run_in_progress` (409, with `details.run_id`), `stale_version`, `idempotency_conflict` and `rate_limited` (429 with `Retry-After`) all behave as specified.
  - Each candidate is a draft version, checked by the independent validator, and never published automatically.
  - An impossible week returns `INFEASIBLE` with `infeasibility.shortages` and a plain summary.
  - Runs are queued on the batch lane, with `poll_after_ms` of 500.

Where the seed and a fixture describe the same data, the live response equals the fixture body; integration tests enforce this. The seed has 20 employees per outlet, while the fixtures have 13, so lists can be longer. Instants come back in the outlet's own offset (`+05:30`).

Run the provider locally (Postgres on the URL in `DATABASE_URL` / `APP_DATABASE_URL`):

```sh
python -m db.init          # migrate to head
python -m seed.v2          # demo tenants (Spice Route Kitchens, Northwind Diner)
DEMO_SESSIONS_ENABLED=true python -m uvicorn api.v2.app:app --port 8000
python -m scheduling.worker  # in a second terminal: solves queued generation runs
```

CORS allows `localhost` and `127.0.0.1` on ports 3000 and 3001. Request missing fields or flows through a handoff note; a contract change bumps `contract_version`.
