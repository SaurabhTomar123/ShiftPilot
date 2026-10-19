# Manual draft editing: 19 October 2026

Task: X3 manual assignment controls and v3 proposal integration.
Status: delivered for existing-assignment form editing; drag gestures and template-based creation remain separate.
Owned files: `web/` only. Backend, database schema and shared planning documents were not changed.
Provider pin: `3.1.0-p4`, 78 fixtures, unchanged from the preceding delivery.

## Delivered behavior

- Copy a published week into an editing draft using the current base version and a stable create-draft key. A lost creation response can be retried explicitly with the same key; a confirmed creation finishes that logical action.
- Choose an existing assignment and reassign/unassign, change skill, move/resize with outlet-local dates and times, lock/unlock or remove. Update requests omit unchanged fields. Break policy stays fixed. The server checks the resulting break, availability, qualifications, minimum staffing and other constraints.
- Preview the exact proposed edit against the reviewed draft revision. Show before/after assignment values, server metrics, required violations and expandable preference messages. Preview does not replace accepted roster data. Any input change clears it.
- Apply only an explicitly reviewed preview without hard violations. Use the returned draft and revision after success. Editing hides proposal approval; closing without edits preserves a pending proposal. A saved new revision requires a fresh proposal review.
- Stale or uncertain saves pause further edits and preserve visible inputs until explicit reload. No apply retry is sent. Unlike create/proposal APIs, applyEdits currently has revision fencing without an idempotent replay guarantee; an Idempotency-Key header alone does not change that fact.
- Keyboard entry, explicit accessible labels, narrow-screen fields, return focus and bounded desktop/phone visual inspection are included.

## Synthetic scope

The default preview remains synthetic. Two request examples are generated from provider fixture metadata: an invalid Tuesday reassignment to Ravi and a valid opening-cook lock. The lock preview combines the provider's before/after assignments, metrics and validation; it does not run a client solver. Unmatched edit requests return a clear missing-fixture response. Apply advances the synthetic draft to the provider's revision 2. Manual drafts then enter the same proposal flow using their actual ids, revision, base and metrics. A fresh proposal after a saved revision gets a distinct synthetic id. State remains bounded, visit-scoped and volatile.

## Verification

Type checking, production build, lint, 119 unit/contract tests and verification of all 78 fixtures passed. The full desktop/mobile browser suite passed 86 cases (2.7 minutes) before the final fixture-only proposal-recovery refinements. All 38 affected manual-edit/proposal cases then passed on the final build (1.3 minutes), including two newly added desktop/mobile revision-change cases: 88 distinct browser cases were verified across these runs. Coverage includes read-only preview, exact reviewed payload, invalid blocking, input invalidation, stale retention, lost-response recovery, create replay, keyboard/axe/viewport checks, a late preview after a week switch and proposal lifecycle after editing.

Real API checks used only the isolated Codex seed database (`shiftpilot_codex`, PostgreSQL port 5435) and API on 8011. A Playwright-only forwarding route removed fixture headers; it did not enable default live mode. Results:

| Check | Result |
| --- | --- |
| Create a manual draft from the published 26 October week | 201 |
| Resume draft by version read | 200 |
| Preview and apply lock | 200 / 200; draft revision 2 |
| Preview and apply unlock | 200 / 200; draft revision 3 |
| Replace successful unlock response with 503 in the browser | UI paused saving and required reload |
| Explicit reload after the lost response | 200; recovered revision 3; no repeated apply |
| Published version pointer | Unchanged throughout manual editing |
| Additional unassign, role, move and remove previews | 200, typed diffs and reported hard violations; no revision/assignment mutation |

The additional previews were API checks, not real successful saves for those operations. Their invalid results are appropriate validation evidence, not evidence that the changes could be published. Publication from an edited revision has synthetic browser coverage; this real manual-edit check deliberately left its draft unpublished. Claude's database and unrelated local applications were untouched.

## Next work and provider requests

- Add template-based shift creation after a usable template catalog/selection contract; do not expose arbitrary break policies from the older AddShift request.
- The editor reviews one assignment change per request and blocks previews with any hard violations. Drafts needing several simultaneous corrections will need a staged batch-edit path or a valid repair candidate.
- Build drag interactions on top of the same preview/apply pipeline, then History/compare/restore and absence repair. This delivery does not claim all of X3, I1/I2 or the v3 MVP complete.
- Claude: align applyEdits/discardDraft with the broader v3 replay convention, or explicitly document their revision-only recovery semantics. Existing candidate detail and acknowledged-cost fixture follow-ups remain in CONTRACT_REVIEW.md.
- Proposal discovery after a page reload still needs a contract/navigation design; this delivery preserves an open proposal when merely closing the editor, but does not introduce a proposal inbox.

Source design: [manual edit flow](MANUAL_EDIT_FLOW.md). Earlier evidence: [candidate/proposal delivery](UI_HANDOFF_V3_REVIEW.md).
