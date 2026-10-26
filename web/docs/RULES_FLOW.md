# Scheduling rules: preview, exceptions and archive

26 October 2026. Codex owns this frontend; Claude owns API, database and engine behavior. Architecture v4 remains governing, with source SHA-256 `1c22563a3953d64faaf8e48cde0ab4c7f08955320415992c8e8d41ac3fd38216` verified unchanged.

## Delivered contract slice

The consumer stays on **3.27.0-p4 / 164 fixtures**, provider `9d176a31cd7a3786e1f9f1cfc6a3d401fa4558ea`. No backend source, runtime, dependencies or provider snapshot bytes changed. Generated `rule-examples.json` derives from the existing preview requests and is verified by the contract generator.

Rules is a destination for users with `manage_employees`. Entry reads the rule catalog including archived records and paginates employees for the selected outlet. The catalog may contain organization, tag and other-outlet rules; the outlet selector controls new outlet rules and person choices, not catalog scope. Managers can define outlet/person rules within their outlet. Only owners see organization/tag choices. The API must enforce these permissions independently.

The typed form supports maximum working days (1–7) and latest shift finish (half-hour grid, selected weekdays, explicit midnight). Rules are required constraints. Notes are optional; no prompt or parsing endpoint is required. Natural-language parsing is separate future work. The browser validates input shape and scope choices; it never calculates effective constraints, priority, conflicts, eligibility or shift impact.

## Review and explicit exceptions

Preview POST is read-only and has no replay key. Its normalized rule definition must match the submitted inputs before any save becomes available. Editing any field discards the preview. The review displays server-reported affected people, conflict messages and overlapping people, and up to 50 upcoming published-shift impacts. Impact timestamps retain each returned UTC offset because one rule can span outlets.

Saving requires `valid: true` and no returned conflicts. The UI never assumes that a narrower scope overrides a broader rule. A server-provided `suggested_exception` can be loaded as the exact next definition, preserving `overrides_rule_id`; loading it clears the previous preview and sends no request. A fresh preview is required before saving that exception. Changing rule type, scope or person clears the exception reference. Availability and absence facts remain authoritative and cannot be overridden through this form.

Create POST sends only the reviewed definition with a fresh idempotency key. It requires an active returned rule matching that definition before announcing success. The catalog upserts by returned ID; it does not duplicate the supplied fixture ID. No existing published assignment is moved and no generate, repair, proposal or publish endpoint is called. Future planning uses active rules through the backend.

## Interrupted writes and archiving

An uncertain create preserves its exact body/key in memory and blocks other mutations. Check rule save reads the catalog; matching text alone does not prove that request completed. Retry same rule save is explicit and reuses the original body/key. Definite rejection discards the actionable preview and requires another preview. No write retries automatically.

Archive has a separate confirmation naming the rule and scope. The contract has no declared archive replay key. If the outcome is uncertain, the UI requires Reload saved rules before another write and includes archived records for inspection; it does not automatically repeat the archive. Successful archive clears an earlier preview because the effective rule set changed.

Scope/persona changes cancel obsolete waits and remount the editor. Pending keys live only in the mounted workflow; recovery across reloads is not claimed. Server revalidation, tenant isolation and idempotency remain backend responsibilities.

## Synthetic coverage and provider follow-up

The supplied owner example previews the student 21:00 weekday tag rule affecting three people across outlets. Its create record uses the same ID as the initial list, so the preview gateway upserts that fixed record rather than fabricating a distinct newly-created rule. An owner can archive it; archived filtering reflects that result. Creating a fresh rule after archive is unsupported rather than inventing recreation.

The supplied Rohit Friday 23:00 example conflicts with that tag rule and contains an explicit suggested exception. There is no successful exception-preview/save fixture, nor matching outlet, organization, maximum-days or published-shift impact examples. Unsupported requests return 501 and never reuse unrelated success data. Browser tests use clearly identified consumer-only variants to verify those rendering/interaction paths; they are not provider or live acceptance evidence. Session state is bounded, expires, and is isolated by persona/preview-session nonce.

Provider follow-up: supply coherent successful exception preview/create records, outlet/person maximum-days examples, multi-outlet impacts, overlapping-rule rejection after a preview, archive conflict/permission cases and tenant-isolation evidence. The typed API integration is delivered; full synthetic coverage and live 3.27 engine/worker/database acceptance remain open.

## Verification

Unit/contract tests cover input bounds, permission choices, exact exception references, identity comparison, timestamp offsets, read-only previews, stable create replay, archive filtering, unsupported fixture behavior and role denial. Browser tests cover desktop/mobile entry, axe, viewport fit, fresh-preview enforcement, exact exception saves under a consumer-only variant, mismatched responses, late conflicts, uncertain-create replay and archive read recovery. Validation passed: 253 unit/contract tests, 246 desktop/mobile browser tests (including 24 Rules checks), lint, production build and contract provenance verification. Desktop/mobile screenshots were inspected; axe and page-overflow checks passed. Live 3.27 API/worker/tenant acceptance was not run.
