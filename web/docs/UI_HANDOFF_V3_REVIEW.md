# V3 candidate and proposal delivery: 19 October 2026

Task: X2.1 / candidate selection and proposal approval under architecture v3.
Status: delivered for this workflow; complete MVP and integration gates remain open.
Owned files: `web/` only. Claude's backend commit `f8837ae` was merged; no backend source was edited by Codex.
Contract: `3.1.0-p4`, 78 generated fixtures. See [consumer review](CONTRACT_REVIEW.md) and [flow design](V3_REVIEW_FLOW.md).

## Behavior

1. Generation returns lightweight candidates. Opening an option performs a candidate GET and shows its assignment diff, constraints, coverage and capability-gated cost. It creates no version.
2. Selecting sends an idempotent POST and opens the returned draft. Saved drafts supplied by a schedule read can also be opened after revalidating their current status.
3. Create proposal records the reviewed draft id/revision and displays the server's proposal status, expiry and metrics at proposal.
4. Approval handles four normal business results. Published triggers a fresh week read. Stale and Invalid retain their reasons and offer an explicit reload. Changed shows typed before/after deltas, leaves the roster unpublished and requires a fresh checkbox acknowledgment before a separate approval action. Reject and proposal status refresh are also available.
5. Writes do not retry automatically. A lost success response retains the key for an explicit retry. Session/week/outlet changes abort old reads, and late results cannot replace a new view. Selection and proposal controls require the publish capability; API authorization remains authoritative.

The Ink/Workshop design and the appearance experiments remain available. Review summaries stack on phones; assignment and delta tables are keyboard-scrollable inside named regions. Desktop and phone visual captures were inspected, and document width stayed within both viewports. No decorative motion was added.

## Verification

Type checking, lint, the production build, 112 unit/contract tests and contract verification for all 78 fixtures passed. All 66 desktop/mobile browser cases passed in the final run (2.5 minutes). Coverage includes read-only review versus selection, proposal request revisions/keys, all four outcomes, rejection, a committed approval whose success response was lost, week-switch cancellation, accessibility and narrow-screen layout.

The isolated Codex database on port 5435 was migrated from 0007 through 0011. Its API on port 8011 and worker were restarted against the merged code. A Playwright-only forwarding route stripped preview headers and exercised the real API from the browser:

| Step | Result |
| --- | --- |
| Generate 26 October week | 202, followed by real worker results |
| Draft count before/after generation | 0 / 0 |
| Read candidate detail | 200 |
| Select candidate | 201, materialized draft |
| Create proposal | 201 |
| Approve proposal | 200, Published |
| Fresh published week read | 200; 71 shifts; 0 reported hard violations |

This modified only the synthetic seeded Codex database: the upcoming week is now published there. Claude's database and other local applications were untouched. The normal preview on port 3001 remains in fixture mode; no tracked environment file enables live mode. This smoke does not establish deployed CORS, authentication, tenant isolation, an infeasible real generation scenario, or real Changed/Stale/Invalid acceptance. Those outcomes have consumer fixture/browser coverage here.

## Boundaries and provider requests

- Balanced is the only detailed candidate/select fixture. The second summary remains visible, but opening it reports missing provider data. The live client supports any contract-shaped candidate.
- The acknowledged Changed fixture publishes a summary with the original recorded cost, despite the preceding changed-cost fixture reporting a higher amount. The consumer preserves provider values. Claude should align those two fixture stories; see CONTRACT_REVIEW.md.
- Pending proposal recovery after leaving/reloading the view needs a proposal discovery/list contract or a deliberate navigation-state design. This slice can refresh a proposal while its review is open and reopen saved drafts; it does not claim a proposal inbox.
- Manual edits, History/compare/restore, absence entry and repair, staffing templates, CSV onboarding and Rules remain future UI integrations. Some backend APIs already exist; their absence from the UI is not a backend blocker.
- The shared board is Claude's planning document. Planning writer can update X2.1 and the proposal portion of X3 with this evidence; do not mark full I1/I2 or all of P3 complete from this smoke.

The earlier [forms/design handoff](UI_HANDOFF_2026-10-19.md) describes the previous 2.3 baseline and remains historical.
