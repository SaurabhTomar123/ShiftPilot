# Find cover: direct replacement review

Updated 26 October 2026. Architecture v4 governs. Codex owns the UI; Claude owns the API, database and scheduling implementation.

## Current contract and runtime boundary

Frontend-only snapshot **3.27.0-p4 / 164 fixtures**, provider `9d176a31cd7a3786e1f9f1cfc6a3d401fa4558ea`, aggregate SHA-256 `9a08294a7af94c7614832002be2087018bc2b768dc41493b4e36cc6f7cd68a4e`. Per-file hashes remain in `web/contracts/v2/SOURCE.json`. No provider source, migration, worker, dependency or database change is included. Earlier 3.19 delivery records are historical; this pin consumes the requested cover-edit fixtures and fairness correction.

## User flow

1. Open Find cover from Schedule or Repair Inbox. Select a published/draft shift and priorities. Only owners can request people from other outlets. The recommendation POST is synchronous and read-only; it has no mutation key or automatic retry.
2. Inspect provider rank, direct/overtime/other-outlet disruption, exact-paise cost against leaving unfilled, added overtime, weekly hours, fairness change and preferred-window status. Missing values stay unreported. Recorded blocked people are separate from eligible options. Cost access applies inside reasons as well as headline metrics.
3. Review a person in draft checks the published base or draft revision, prepares a copy when needed and validates the returned edit. Preparing a draft does not apply the replacement. Locks require separate explicit editor review.
4. Save replacement to draft sends the exact reviewed edit/revision once. The chosen draft enters normal proposal review. Only explicit proposal approval publishes. Hard-invalid previews block saving; stale/uncertain saves require reading the current draft before another edit.

## Supplied cover story

The default preview now supports the complete provider story: Ravi Kumar's Prep assignment on 21 October at Indiranagar, Balanced, Chitra Indiranagar selected. It consumes `draft.create.cover`, `edits.preview.cover`, `edits.apply.cover` and the existing proposal/approval flow. The cover draft has its own provider ID; the opening-lock example keeps its original manual draft ID. Base, logical shift, selected person and revision are preserved through publication.

Both draft examples use the same declared create body. A call-scoped `X-ShiftPilot-Draft-Example: cover` header selects the supplied cover story only at `/api/fixture`; it is never sent to a configured real API and adds no backend request field. Persona/session state remains bounded and expiring. This is synthetic story selection, not a new provider capability or authorization mechanism.

The provider's UpdateShift contract now explicitly states: omitted or null fields keep existing values, except `employee_id: null`, which unassigns. Removing a break uses `break_minutes: 0`. The preview matcher accepts omitted/null non-assignee fields equivalently only for the exact supplied cover edit. It preserves start/end, role, break time and duration. Other people, times, roles or unknown fields do not receive fabricated validation/save results.

Aman is still a returned recommendation, but no matching save record is supplied for him; preparing that option retains its draft and reports the preview limitation. Rule-conflict, stale-revision and unsupported-edit checks remain explicit. No frontend eligibility, ranking or solver validation is inferred.

The preview retains conservative revision-fenced edit recovery. Full provider apply-edits replay semantics are not implemented in this gateway; the UI does not automatically repeat an uncertain save.

## Fairness correction and streaming fixtures

The supplied Balanced burden is 7.97 and Lowest cost is 7.83. The corrected requested-plan fairness delta is **-0.14**, now consumed without a warning. The consistency guard remains active and is tested using an injected disagreement, without changing provider bytes or client-side rescoring.

The snapshot also includes P1 and SSE schemas. All 164 response records are schema-checked, including decoded EventStream frames against their declared `text/event-stream` contract. This validates fixture data, not wire framing, reconnection, authorization or a live streaming client. Runtime progress still uses bounded polling; P1 UI integration remains separate.

## Verification and remaining acceptance

Unit/contract coverage verifies exact cover request/revision, preserved breaks/times/role, read-only preview, stale revision, blocked/unsupported edits, unchanged published pointer before approval, proposal identity and fixture-header confinement. Browser coverage exercises the provider-backed preview/save/proposal/approval path on desktop and phone, plus the existing lost-response/current-fact/privacy checks. Artificial response tests are labelled local consumer checks; the main Chitra success story now uses the provider records throughout.

Verified: 235 unit/contract tests, all 164 provider response records and source hashes, TypeScript/production build and lint. The shared browser regression is checked before the feature push.

Live 3.27 API/solver/tenant/deployment acceptance remains pending. Earlier real API checks refer to the reviewed 3.3 runtime. Scenario Lab's completed-run/detail fixture and public event-revision gaps remain open; see SCENARIO_LAB_FLOW.md.

Next consumer work: remaining template/import/rule and P1 demand/employee workflows against their published contracts. SSE runtime consumption and broader live backend integration are separately reviewed milestones.
