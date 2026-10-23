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

## What changed in 3.21.0-p4 (live): conflict-set diagnosis (architecture v4 §17)

This change is additive.

- **`Infeasibility.conflict_set`:** when no valid roster exists, the run also names the business constraints that together cause it. These come from CP-SAT's sufficient infeasible assumption set.
  - Kinds: `minimum_coverage` (skill and day), `no_overtime` (person), `rule` (person and rule id), `labour_cap` (scenarios).
  - Each item has a deterministic `message` and the `relaxation` it offers, e.g. "Allow overtime for this person."
- **What it is not:** it is a diagnostic set, not a claim of the smallest one. Facts (availability, absences), mandatory skills, safety caps (maximum weekly hours, rest, overlap) and pins are never in it. When facts alone make the week impossible, it lists only the minimum-staffing constraints that cannot be met.
- **Alongside the existing fields:** shown with `shortages` (the capacity gap) and `options` (relaxations already tested to be feasible). Scenario runs get it too, e.g. an impossible labour cap.

Fixture: `run.infeasible` carries a conflict set.

## What changed in 3.20.0-p4 (live): Scenario Lab (architecture v4 §23, §42)

This change is additive. Migration `0019` adds `planning_scenarios` and `scenario_events`.

- **The flow:** create a what-if on a week → add events → run → compare → "Turn this into a plan" (convert) or discard.
  - `POST /v2/outlets/{outlet_id}/schedules/{week_start}/scenarios` takes `{title, events}` and starts from the week's current published version.
  - `GET /v2/outlets/{outlet_id}/scenarios?week_start=` and `GET /v2/scenarios/{id}` read scenarios.
  - `POST /v2/scenarios/{id}/events` adds an event.
  - `POST /v2/scenarios/{id}/run` (Idempotency-Key) returns `202` with an `OptimizationRun` of `kind: "scenario"` and a `scenario_id`.
  - `POST /v2/scenarios/{id}/convert` (Idempotency-Key, `{candidate_id}`) returns `201` with a draft.
  - `POST /v2/scenarios/{id}/discard`.
- **Event types:** `demand_change` `{percent, skill_id?, weekdays?, start_minute?, end_minute?}`, `absence` `{employee_id, start_at, end_at}`, `outlet_closure` `{day}`, `labour_cap` `{max_cost_paise}`, `rule` `{rule_type, parameters, employee_ids}`. Anything else gets a `422` that names the field, e.g. `["events", 0, "type"]`.
- **Isolation:** events are overlays applied only while the solver input is built. Nothing is written to absences, availability, rules or staffing requirements; integration tests assert those tables are unchanged.
- **Comparing:** `Scenario.baseline` is the current plan under the events: its metrics, plus the hard violations the events cause (e.g. `absent`, `minimum_coverage`). Each candidate's `trace.summary` is its delta against the base version under the same events.
- **Scenario candidates cannot be selected:** `selectOptimizationCandidate` returns `409 conflict` with `details.scenario_id`. Convert instead.
- **Convert re-checks against current facts:**
  - `409 stale_version` when the real week moved since the run.
  - `409 conflict` with `details.violation_codes` when the plan only works under the scenario's assumptions (e.g. a closed-Saturday plan breaks real minimum staffing).
  - Otherwise it creates a normal draft with `source: "scenario"`, which follows the usual proposal and publish path.
- **Running:** scenario runs queue below repairs and above batch generation. One worker process stays repair-only. Open scenarios expire after 7 days (`status: "expired"`), and every change returns `409` once a scenario is converted, discarded or expired.

Fixtures: `scenario.create`, `scenario.create.invalid_event`, `scenario.event.add`, `scenarios.list`, `scenario.run.accepted`, `scenario.get` (with baseline), `scenario.convert`, `scenario.convert.assumptions`, `scenario.discard`, `candidate.select.scenario`.

## What changed in 3.19.0-p4 (live): replacement recommendations (architecture v4 §11, §46)

This change is additive.

- **New endpoint, `POST /v2/recommendations/replacements`:** body `{version_id, logical_shift_id, profile, include_other_outlets, limit}`. It answers "who can cover this shift?" for a published or draft version. It is synchronous and read-only; nothing is written.
- **Eligibility comes first.** Each qualified person is checked by the independent validator as a direct assignment: they take the shift and nothing else changes (`basis: "direct_assignment"`). People a rule blocks are listed in `rejected` (up to 10) with the concrete fact and its `rule_ids` or `absence_ids`. They are never ranked.
- **Ranking:** first by `disruption_class` (`direct`, then `overtime`, then `cross_outlet`), then by the chosen `profile` on the solver's own scale: incremental cost, fairness penalty, working outside a preferred window and hours alignment.
- **Each recommendation includes:**
  - `incremental_cost` against leaving the shift open, `overtime_minutes_added`, `fairness_delta`, `weekly_minutes_after` and `within_preferred_window`;
  - `reasons`;
  - a ready-made `edit` (`{op: "update", logical_shift_id, employee_id}`). Apply it to a draft with `applyEdits` to choose that person; it then follows the normal proposal and approval path.
- **Errors:**
  - `include_other_outlets` is owner-only: managers get `403`.
  - A shift that isn't in the version: `422`.
  - An unknown version: `404`.

Fixtures: `recommendations.replacements` (the same Wednesday shift as the repair story; the repair candidate gives it to the person ranked first), `recommendations.replacements.other_outlets.manager` (403), `recommendations.replacements.unknown_shift` (422).

## What changed in 3.18.0-p4 (live): decision trace (architecture v4 §18)

This change is additive.

- **`Candidate.trace`:** every new candidate, from generate or repair, carries `{strategy, summary, counts, explained_shifts, explanations_truncated}`. It is null on candidates stored before 3.18.
  - **`summary`:** `cost_delta_paise`, `preferred_gap_delta_minutes`, `fairness_delta`, `overtime_minutes`, `cross_outlet_moves`, `changed_commitments`. When there is a published base, deltas compare with it (`compared_to: "base_version"`). On an empty week, other plans compare with the requested plan (`"requested_plan"`); the requested plan's own deltas are null. Negative deltas mean cheaper, better covered or fairer.
  - **`counts`:** the v4 taxonomy, `KEPT`, `MOVED_TIME`, `REASSIGNED`, `CREATED`, `REMOVED`, `UNFILLED`.
- **`CandidateDetail.trace_changes`:** the class of every non-kept shift, in time order.
- **Explanations:** these now also come with regeneration over a published week, not just repairs. They cover reassigned, created and unfilled shifts, up to 30 (`explanations_truncated`).
  - **New fact codes for the chosen person:** `incremental_cost`, `fairness_burden`, `disruption`.
  - **New `rules` fact for everyone:** an alternative blocked only by a scheduling rule used to show as `eligible_not_selected`. It is now `rejected`.
  - **Provenance:** blocking facts carry `rule_ids` and/or `absence_ids`.

Fixtures: `run.succeeded`, `candidate.detail`, `candidate.detail.repair` and `run.repair.widened` carry traces computed by the backend's own code.

## What changed in 3.17.0-p4 (live): Candidate Portfolio (architecture v4 §16)

This change is additive.

- **Strategy names:** generation adds `stability` and `fairness` to `Strategy`; the existing names keep working. Labels are Stability, Lowest cost, Employee fairness and Maximum coverage. `fairness` is a real fairness solve: it minimizes the burden imbalance, not hours alignment.
- **Which strategies run:** a generate run solves the requested strategy, then the portfolio's: `stability` (only when there is a published week to keep stable), `lowest_cost`, `fairness`, `max_coverage`.
- **How plans are chosen:**
  - The requested strategy's plan is always rank 1.
  - The others are dropped as duplicates (same assignments), on a guardrail, or as dominated (another plan is no worse on cost, preferred-coverage gap, overtime, changed shifts and fairness burden, and better on one).
  - At most three plans are shown.
- **`OptimizationRun.portfolio`:** `{policy_version, considered, dropped: [{strategy, reason, detail}]}` explains every strategy not shown, e.g. "Maximum coverage was left out: it costs more than 1.4x the requested plan". It is null for repairs.
- **Guardrails, policy 1,** measured against the requested plan:
  - Stability: cost ≤ 1.1×, and overtime no more than 4 h above the requested plan.
  - Lowest cost: preferred-coverage gap ≤ 3× + 240 staff-minutes; fairness burden ≤ +1.0; changed shifts ≤ +(4 + 20% of the base).
  - Employee fairness: coverage gap ≤ 1.25× + 240 staff-minutes; the same changed-shift bound.
  - Maximum coverage: cost ≤ 1.4×, and overtime no more than 8 h above the requested plan; the same changed-shift bound.

Fixture: `run.succeeded` now carries a `portfolio`.

## Fixtures added under 3.16.0-p4 (no schema change)

- **Requested leave, every transition:** `absence.update.requested.confirm` (manager; lists the affected shifts and starts a repair), `.reject` (manager), `.cancel` (the employee withdrawing it). Errors: `absence.update.withdraw_conflict` (409, the employee withdraws after a manager decided), `absence.update.already_closed` (409, deciding a rejected or cancelled record).
- **`absence.report.requested`** now lists the shift the leave overlaps. The server always computed this for requested records; `repair_suggested` stays false until it is confirmed.
- **Repair candidates:** `candidate.detail.repair` (one changed shift, against the published base) and `candidate.select.repair` (the draft: `source: "repair"`, `base_version_id` = the published version). `run.repair.widened` now carries the same candidate, with real metrics.

## What changed in 3.16.0-p4 (live): fairness burden (architecture v4 §12)

This change is additive. Every `Metrics` now has **`fairness_burden_deviation`**: across the outlet's staff, the mean absolute deviation of burden points per 40 h of regular capacity, over the last 8 published weeks plus the week shown. Points come from versioned policy 1: a closing shift (ends at 22:00 or later) 3, a weekend shift 2, a second shift on the same day 2, each overtime hour 1. Lower is fairer. Label it "fairness burden"; it is not hours-preference alignment. **`fairness_components`** breaks the week's burden points down as `{policy_version, closing, weekend, split, overtime}` (this week only, everyone at the outlet), so a candidate's delta from the baseline can be shown component by component. The `staff_friendly` profile now weighs it (15%). The dedicated Fairness strategy arrives with the candidate portfolio.

## What changed in 3.15.0-p4 (live): freeze and pin (architecture v4 §13, §15)

Architecture **v4** now governs. This change is additive.

- **`GenerateRequest.freeze` / `RepairRequest.freeze`:** `{shift_ids, employee_ids, days}`. The published shifts these select are held exactly as they are for this run only; nothing is stored as a lock. The run echoes them in `frozen_logical_shift_ids`. Errors:
  - `422`: freezing an empty week, or pinning a shift that isn't in the published week;
  - `409 conflict` with `details.frozen_logical_shift_ids`: a current fact (an absence, unavailability, a rule) or the repaired absence itself breaks a frozen shift. Unfreeze it or authorize the change.

  Fixture: `repair.freeze_conflict`.
- **Repair runs start with a new stage, `impact`:** it frees only the shifts the absence breaks and freezes everything else (e.g. "Arjun replaces Ravi"), then widens as before. Every `RepairStage` now says what it `released` and, after the first, why it widened (`widened_because`). Fixture: `run.repair.widened`.

## What changed in 3.14.0-p4 (live): language shortcuts

This change is additive (architecture v3 §33–34). Language is a shortcut: every operation still has its form.

- **`parseCommand` `POST /v2/commands/parse`:** body `{text, outlet_id?, employee_id?}`. Supported requests:
  - "Give Ravi Saturday off" (`give_time_off`);
  - "Asha is sick tomorrow" (`report_sick`);
  - "Generate next week" (`generate_week`).

  The answer is a **preview that writes nothing**. With `status: ready`, show the `summary` and confirm by making `action` (the existing `reportAbsence` or `generateSchedule` call, with an `Idempotency-Key`). `needs_clarification` asks a `question` with `options` (e.g. "Which Ravi?"); re-send the same text with the chosen `employee_id`. `unsupported` and `unavailable` point to the form. Fixtures: `commands.parse`, `.which`, `.unavailable`.
- **`parseRule` `POST /v2/rules/parse`:** a rule in words, compiled and run through `previewRule`. With `status: ready`, `preview.rule` is what `createRule` saves. Unsupported rules are refused, never approximated. Fixtures: `rules.parse`, `.unsupported`.
- **Resilience:** the model is called through one adapter with an 8-second timeout, at most two retries with jitter, a circuit breaker and a concurrency cap. When it's down, these endpoints say `unavailable` and nothing else is affected. Deployments enable it with `LANGUAGE_MODEL` (a LiteLLM model string).

## What changed in 3.13.0-p4 (live): scheduling rules

This change is additive (architecture v3 §21). Rules are made in forms now; the language shortcut comes next.

- **Rule types:** `max_shift_end_time` `{latest_end_minute, weekdays}` and `max_days_per_week` `{days}`. Every rule is hard. Unsupported types are a `422`.
- **Scope:** `organization`, `outlet` `{outlet_id}`, `tag` `{tag}` (e.g. `student`) or `employee` `{employee_id}`. There is **no numeric priority**: a more specific rule replaces another only when it names it in `overrides_rule_id`. Facts beat rules: availability and absences are never overridden.
- **`previewRule` `POST /v2/rules/preview`:** writes nothing. Returns `summary`, `affected` people, `conflicts` (in business terms, each with a `suggested_exception` when one person is in both) and `impact` (upcoming published shifts the rule would break). Fixtures: `rules.preview`, `rules.preview.conflict`.
- **`createRule` `POST /v2/rules`:** activates the rule. A conflicting rule is `409 conflict` with `details.conflicts`. Offer "Keep the existing rule" or "Create an exception for <name>" by sending `suggested_exception`. Organization and tag rules are owner-only; managers set rules for their outlet or its employees.
- **`listRules`** and **`archiveRule`**.
- **Enforcement:** active rules bind generation and repair, and the validator reports them as violation code `rule` (with `facts.rule_id`), including on published weeks evaluated against current facts. Published versions are not changed.

## What changed in 3.12.0-p4 (live): private demo sandboxes

This change is additive (B6.2). Each `createDemoSession` without a `sandbox_id` now gives the visitor a **private copy** of the synthetic organization. The response's `sandbox_id` and `sandbox_expires_at` (2 hours) describe it. Send `sandbox_id` back with another `persona` to switch persona inside the same sandbox; once it has expired, that request returns `404`. What visitors change is visible to nobody else, and the whole sandbox is deleted when it expires (the token never outlives it). Sandboxes allow 2 active optimization runs (`429` beyond that), and the number of live sandboxes is capped (`429` with `Retry-After: 60`). Fixtures: `session.demo.manager`, `session.demo.switch_persona`.

## What changed in 3.11.0-p4 (live): in-app notifications

This change is additive (architecture v3 §40). A separate relay process (`python -m jobs.outbox_relay`) turns committed events into in-app notifications. A failing notification can never fail the change that caused it.

- **`getMyNotifications` `GET /v2/me/notifications?unread_only=`:** the caller's inbox, newest first. Each item has a `topic`, a ready-to-show `title`, and a `payload` with ids to link to. Recipients:
  - `schedule.published`: staff with shifts in the new version.
  - `run.finished`: a repair goes to the outlet's managers and owners; options go to whoever requested them.
  - `absence.reported`, `proposal.ready` and `proposal.stale`: managers and owners.
- **`markNotificationRead` `POST /v2/me/notifications/{id}/read`:** idempotent.
- **Delivery:** at least once with duplicate suppression, so one notification per event and person in normal operation. Poll the inbox; there is no push channel in the MVP. Fixtures: `me.notifications`, `me.notifications.read`.

## What changed in 3.10.0-p4 (live): employee self-report

This change is additive. Architecture v3 §20 scopes employee requests for the MVP to self-report; leave balances, swaps and availability-change requests come later.

- **`getMyAbsences` `GET /v2/me/absences?from&to`:** the employee's own absences and requests, any status. Staff only. Fixture: `me.absences`.
- **`MyWeek.absences`:** the employee's own absences overlapping the week, shown next to their shifts.
- **Withdrawing a request:** `updateAbsence` with `{"status": "cancelled"}` now lets an employee withdraw their **own** request while it is still `requested`. A request that was confirmed or rejected is `409`; another person's is `404`. Confirming and rejecting stay manager-only.

## What changed in 3.9.0-p4 (live): employee CSV onboarding

This change is additive (architecture v3 §19). The flow is upload → row-level errors → fix and upload again → commit in one transaction.

| Operation | What it does | Fixture |
|---|---|---|
| `getEmployeeImportTemplate` `GET /v2/imports/employees/template` | Returns the fixed `columns`, one valid `example` row and the rules (`notes`). There is no column mapping. | `imports.template` |
| `stageEmployeeImport` `POST /v2/imports/employees` | Body `{filename, content}` (CSV text, up to 1 MB and 1000 rows) plus `Idempotency-Key`. It validates every row and **writes no employees**. `status` is `staged` (all valid) or `invalid`, with per-row `errors[{column, message}]` and file-level `file_errors`. A manager may only import staff for their own outlet. | `imports.stage`, `.stage.invalid` |
| `getImport` `GET /v2/imports/{id}` | Re-reads a staged import. Staged imports expire after 24 hours. | `imports.get` |
| `commitImport` `POST /v2/imports/{id}/commit` | Creates every employee, with their roles and weekly availability, in one transaction. `409 conflict` when the import is invalid, expired or already committed (`details.status`), or when a row no longer fits (`details.rows`). Imported staff have no overtime; change that per employee afterwards. | `imports.commit` |

## What changed in 3.8.0-p4 (live): infeasibility options

This change is additive (architecture v3 §13). An `INFEASIBLE` run's `infeasibility.options` now lists business options instead of a bare error. Each option was found by re-solving with that single relaxation, and they come in this order:

| `kind` | Meaning | How a manager applies it |
|---|---|---|
| `overtime` | The named `employees` would need `minutes` beyond their regular week. | Allow overtime on those employees (`updateEmployee`), then generate again. |
| `cross_outlet` | The named `employees` from other outlets would cover it. | Owner decision: add them to the week (edits or a repair with `allow_cross_outlet`). |
| `reduced_minimum` | Operate the listed `shortages` with `max_assignable` staff. | Lower `minimum_required` for those intervals (`putStaffingRequirements`, `source: manual`), then generate again. |

Show the `summary` text as given; it is built from the facts and is ASCII. No option is claimed to be the smallest change. Overlap, availability, absences, mandatory skills, the absolute weekly cap and authorization are never relaxed. Rule relaxations will be added with configurable rules. Fixture: `run.infeasible`.

## What changed in 3.7.0-p4 (live): retention

This change is additive (architecture v3 §25).

- **`OptimizationRun.candidates_expired`:** unselected candidates are removed 7 days after their run, and a selected one goes with its draft once that draft has been discarded and purged. A finished run can then show `succeeded` and `OPTIMAL` with few or no candidates. When `candidates_expired` is `true`, say the options expired and offer a new run. Fixture: `run.candidates_expired`.
- **Proposals:** a pending proposal is recorded as `expired` by the daily job after its expiry. Non-approved proposals disappear 30 days after their decision.
- **Discarded drafts** are deleted 7 days after discard. Drop links to them after a 404.

## What changed in 3.6.0-p4 (live): staffing templates (architecture v3 §18)

- **`listStaffingTemplates` / `putStaffingTemplates` `/v2/outlets/{id}/staffing-templates`:** the outlet's weekly default demand, as blocks of weekday × start and end (on the 30-minute grid) × role → `minimum_required` and `preferred_required`. `PUT` replaces the whole set with `base_revision`: a stale base is `409 stale_version` with `details.current_revision`, and overlapping blocks for one weekday and role are a field-level `422`. Saving a template changes no week until that week is expanded. Fixtures: `staffing_templates.list`, `.put`.
- **`expandStaffingRequirements` `POST /v2/outlets/{id}/staffing-requirements/expand?week_start=`:** body `{base_demand_revision, use_demand_bands}` plus `Idempotency-Key`. Regenerates the week's `template` rows, and `band` rows if bands are requested, from the template. **Manual overrides survive.** It returns the week's requirements with a bumped `demand_revision`. Fixture: `staffing.expand`.
- **`StaffingInterval.source`** gains `template` and `forecast`. The seeded weeks are now `template` rows; they were `band`. When a manager changes an interval, send it as `manual` so re-expansion keeps it.
- **`demand_revision` is a true outlet-week counter.** It can't go back when a week's rows are rebuilt.

## What changed in 3.5.0-p4 (live): answers to the manual-edit review

This change is additive.

- **`listShiftTemplates` `GET /v2/outlets/{id}/shift-templates`:** the outlet's active shift shapes: `start_minute`, `duration_minutes`, `break_minutes` and `break_start_minute`, which is where the server places the break. Fixture: `shift_templates.list`. Staff get `403`.
- **New edit `add_from_template`:** `{op, template_id, day, employee_id?, skill_id?, locked?}`. The server derives start, end and break from the template, the same way the solver does, so no client chooses a break policy. `day` is outlet-local and must fall in the draft's week. `skill_id` is required when the template allows any role. Errors are field-level `422`s at `edits[i].template_id`, `.day` or `.skill_id`. It works in both `previewEdits` and `applyEdits`.
- **Replay on `applyEdits` and `discardDraft`:** these now accept an optional `Idempotency-Key`. With a key, a repeat returns the stored result after authorization and before the revision check, so a save whose response was lost can be retried safely. The same key with a different body is `409 idempotency_conflict`. Without a key, only revision fencing applies. Always send one; it will become required in 4.0.
- **Several corrections at once:** a single `EditRequest` already takes up to 200 edits. They are previewed and applied together, and validated as a whole, so a draft that needs several simultaneous fixes doesn't need one valid intermediate state per edit.

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
