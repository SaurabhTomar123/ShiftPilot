# Weekly staffing templates and dated expansion

26 October 2026. Codex owns this UI; Claude owns API, database and scheduling implementation. Architecture v4 remains governing; the local source still matches SHA-256 `1c22563a3953d64faaf8e48cde0ab4c7f08955320415992c8e8d41ac3fd38216`.

## Contract and delivery

The consumer remains pinned to **3.27.0-p4 / 164 fixtures**, provider `9d176a31cd7a3786e1f9f1cfc6a3d401fa4558ea`. No provider snapshot bytes, backend implementation, worker, migration, dependency or database state changed in this slice. A generated client-only template example is derived from the existing `staffing_templates.put` request; the normal provenance/check workflow verifies it.

Staffing now contains a native Weekly staffing template disclosure. The original dated editor remains below it. Initial entry performs reads only. Templates belong to the outlet across weeks; dated requirements belong to the selected outlet/week.

## Editing a recurring pattern

- Filter by weekday and skill, add/remove blocks, edit start/end and minimum/preferred counts. All inputs stay on the half-hour grid. Midnight is explicit; overnight staffing must be split across weekdays because the contract ends blocks at 1440 local minutes.
- Validation checks known skills, weekdays, whole nonnegative counts, preferred >= minimum, same-day ordered bounds, max 2000 blocks and overlaps within the same weekday/skill. Adjacent blocks and different skills may overlap. Validation never mutates the set.
- Save weekly template sends the complete set with its base revision, including blocks hidden by filters. Saving does not write dated requirements, generate a roster or publish. An empty set is clearly described as removing the recurring pattern while leaving dated requirements in place.
- Read-only scheduling access disables editing and expansion. Scope changes cancel obsolete waits. Returned template outlet identity must match the selected outlet.
- Save failures preserve inputs and require an explicit template reload before another save or expansion. Reload deliberately replaces unsaved template edits. Template PUT has no declared replay key; it is never retried automatically.

## Expansion and recovery

Review expansion request is a read-only summary: outlet/week, observed template revision, current demand revision, saved block count, current manual interval count and optional demand-band use. It is not a locally computed expansion, staffing preview or solve. Demand bands apply saved order-volume mapping where observations exist; the toggle does not import observations or run forecasting.

Unsaved dated edits or template edits block expansion. Dated staffing has an explicit reload action. Template mutations and dated mutations are disabled while the other operation is active.

The final expansion action re-reads the saved template and stops if its observed revision changed. It then sends `ExpandStaffingRequest` with the reviewed `base_demand_revision` and a fresh key. The API replaces template/band rows while preserving manual overrides and other retained sources. The UI displays the returned dated rows and demand revision without reproducing this backend calculation. No generate, proposal or publication endpoint is called.

The public expansion body does not include a template revision. The preflight read therefore does not atomically fence a concurrent template save between that read and the POST. The review states that the server uses the saved template current when expansion runs. Provider follow-up: consider an expected template revision for an atomic conflict check and publish corresponding stale-template acceptance records. This UI does not claim such an atomic guarantee.

An uncertain expansion retains its original body/key and locks further template and dated writes. Check dated staffing sends a read only; a higher demand revision alone is not treated as proof that this request succeeded. Retry same expansion is explicit and reuses the original key/body, without a new-template preflight that could prevent replay. Confirmed success unlocks editing and replaces the displayed dated requirements. Stale/conflict responses clear the actionable request and offer explicit reload; writes are never automatically repeated.

Keys exist for the current mounted workflow only. Leaving the scope cancels its waits; there is no claim of durable browser recovery across reloads. The API remains authoritative for revisions and idempotency.

## Honest synthetic examples

The existing template-list fixture has 88 blocks at revision 1. The template-save fixture raises Saturday Grill 18:00-22:00 from minimum/preferred 1/3 to 2/4 and returns template revision 2. The UI can load this complete supplied example for review, then save it. The dated week remains unchanged at demand revision 3.

The supplied `staffing.expand` record also starts from demand revision 3, but its output still reflects the original template: Saturday Grill remains 1/3. It contains no manual rows or demand-band results. The gateway therefore supports that expansion only for the original template/week without manual changes or bands. It returns the byte-sourced provider result at demand revision 4 and supports keyed replay without another revision bump.

The gateway refuses to substitute that original result after saving the changed template, after editing dated rows or with bands enabled. It does not fabricate an expansion algorithm or manual-preservation result. The UI explains the limit and preserves the user's edits. Other outlet/week examples are explicitly unsupported; manager/staff scope denial remains enforced.

Provider follow-up: add coherent save-then-expand records for the changed Saturday pattern, manual overrides, demand bands, empty sets and stale template/demand revisions. Current schemas/endpoints are already integrated; this is a coverage request, not a claim that the API is absent.

## Verification and remaining work

Unit/contract tests cover block validation, whole-set save, unchanged dated facts, scoped access, exact revision/key, replay and unsupported example combinations. Browser checks cover desktop/phone accessibility and overflow, filtered whole-set save, invalid input, review versus write, unsaved dated guards, lost-response recovery, stale template detection, late outlet reads and read-only access.

The manual-row browser case uses an explicitly labelled local response variant to verify that the consumer retains returned manual rows. It is not live evidence that the backend preserves them. The supplied provider expansion example is tested separately.

Verified for this slice: **242 unit/contract tests**, source hashes and all 164 provider responses, TypeScript/production build and lint. The shared browser regression is checked before the feature push. Local visual captures are ignored under `.impeccable/review/`.

Live API, concurrent-save, timezone/DST, tenant and deployment acceptance remain open. Earlier real API checks describe the reviewed 3.3 runtime only. No backend runtime was upgraded or exercised for this delivery. Next consumer work is the remaining import/rule and employee/demand workflows; Scenario Lab's terminal-run/event-provenance fixture gaps remain separately documented.
