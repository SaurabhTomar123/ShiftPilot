# History and restore: 21 October 2026

Task: version history, comparison, restored-draft review and pending proposal recovery.
Status: delivered for these UI workflows; full v3 release acceptance remains open.
Owned source changes: `web/` only. Claude baseline `d66ad33` was merged; Codex did not edit provider/backend source.
Provider pin: **3.3.0-p4**, 83 generated fixtures. Provider 3.11 exists upstream but is not integrated or approved by this slice.

## Behavior

- History is a real desktop/mobile destination scoped to the selected outlet and week. Staff navigation still exposes only their own schedule.
- Version rows show source, status, revision, dates, recorded coverage and capability-gated recorded cost. Missing recorded metrics are stated instead of recomputed. Current-fact comparison metrics are labelled separately.
- Comparison selects an explicit From and To direction and shows typed before/after assignment changes. New comparison inputs clear the previous result. Empty, denied, unsupported and late-response states do not retain another week's history.
- Restore names the source and current published base before the explicit action. It sends expected_base_version_id and a stable idempotency key. Stale results keep the choice visible and require reload; a lost response can be retried explicitly with the same key. No automatic write retry or optimistic publication.
- The returned restored draft shows current validation, metrics and assignments. Hard violations block proposal creation. A valid draft enters the existing proposal approval workflow. Going to Schedule makes the saved draft available there.
- History discovers pending proposals. Reopening reads both proposal and current draft before showing approval, and refuses mismatched revisions. A real pending proposal was also recovered in a fresh browser session.
- Both candidate detail/select examples are now available. The acknowledged-cost fixture fix is consumed and regression-checked. Synthetic published employee-hour totals are derived from the published fixture assignments, so restoring the older plan does not keep stale row totals.

## Verification

Type checks, lint, the production build, 127 unit/contract tests and verification of all 83 provider fixtures passed. The initial 106-case desktop/mobile run passed 104 cases; two denied-state cases had an incorrect expected message in the test. After correcting it, all 18 History cases passed. All 56 affected history/proposal/manual-edit cases then passed on the final build after the fixture-total correction (1.7 minutes). Thus all 106 distinct browser cases were verified across the full and targeted runs. Coverage includes comparison direction, missing historical metrics, hard-invalid restoration, stale/lost responses, explicit approval, proposal discovery, week-switch cancellation, keyboard regions, axe and viewport checks. Desktop and phone history/comparison/restore captures were inspected.

## Isolated real API evidence

Only the Codex seed database on port 5435 (`shiftpilot_codex`, container label `shiftpilot.owner=codex-ui`) was used. The existing Codex API was verified and restarted on 8011 with the reviewed 3.3 code. No migrations were needed for this contract change. Claude's database and unrelated applications were untouched.

The real seed initially had only one published version for 19 October. Test setup copied seed version 1 and explicitly approved the copy as version 2 in this isolated database, creating an older history entry. The subsequent browser test forwarded requests to the API only through a Playwright route that stripped preview headers:

| Step | Evidence |
| --- | --- |
| List history and pending proposals | 200 |
| Compare current version 2 with version 1 | 200; identical copied assignments, so no assignment diff |
| Restore version 1 | 201; new draft version 3 |
| Read published week after restoration | Published version 2 unchanged |
| Create restored draft's proposal | 201 |
| Leave the view, rediscover and reopen pending proposal/draft | 200 |
| Reopen pending review in another fresh browser session | Passed; no approval sent |

Thus the setup did publish a synthetic version 2, while the restore itself did not publish. Draft version 3 and its pending proposal remain in the isolated database. The ordinary UI remains fixture mode; no tracked environment file enables live API mode. The live check does not establish deployed CORS, full authentication/tenant isolation, real stale/invalid races, or complete release acceptance. Those failure presentations have consumer/browser fixture coverage here.

## Boundaries and next work

- Synthetic comparison fixtures cover versions 3 and 4 in both directions. Restoration uses the provider version-2 story based on published version 3. Other fixture combinations return a clear unsupported response; the live client supports general contract-shaped versions.
- Synthetic history begins with the provider's declared snapshot, which already includes example drafts. It is not an audit of clicks in this browser. Proposal mutations remain volatile and visit-scoped; a full fixture-page reload starts another preview session. Real API proposal state persists on the server.
- Later profile, template, replay, CSV, employee self-report, retention and notification contracts remain to be reviewed and integrated. The 3.5 replay/template responses resolve earlier provider requests upstream; they are not missing backend work.
- Next UI integrations are absence reporting/repair and the next contract upgrade for template-based additions and replayable editing. Rules, onboarding, notifications, drag interactions and full release gates remain separate work. Do not mark the entire MVP complete from this delivery.

Design intent: [History flow](HISTORY_FLOW.md). Contract acceptance: [consumer review](CONTRACT_REVIEW.md). Prior evidence: [manual edit handoff](UI_HANDOFF_MANUAL_EDITS.md).
