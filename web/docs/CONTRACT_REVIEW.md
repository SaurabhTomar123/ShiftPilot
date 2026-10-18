# X0.3 consumer review: scheduling contract 2.1

Provider: Claude. Consumer: Codex. Version reviewed: **2.1.0-p1p2** on 18 October 2026, from commit `a4d6f0e` (including provider commit `ab96aa9`).

**Decision: approved for the declared P1–P2 consumer scope.** Publication, edit validation, repair, history, rules, CSV import and employee requests need their later contracts; this approval does not invent or approve those APIs. No live-provider integration gate is closed: the provider routes still declare `501 not_implemented`.

## Evidence

- Generated TypeScript paths/components from the provider's OpenAPI 3.1 document; no shared contract was edited.
- Generated frontend registry contains **39** fixtures, the count in the current provider index. Older planning references to 40 are not the current measured count.
- `npm run contracts:check` verifies the schema, index and every fixture against a committed SHA-256 manifest. Current hash: `0bc131acf48762e0c5e7cfaf6425dfce502fdd587bdbc42fd86947e89121c565`.
- Independent JavaScript/AJV 2020 consumer tests parse all 39 response bodies against their named provider schemas. The complete unit/contract suite has 57 tests.
- Browser consumer flows cover published read, empty week, generate/candidate preview, FEASIBLE versus OPTIMAL, UNKNOWN versus INFEASIBLE, stale writes, denial, persona change and session expiry.

## Conventions accepted

- Bearer token stays in memory. Persona changes abort outstanding UI requests and discard old session/view state. A 401 clears credentials and shows recovery.
- Capability-driven controls; the server still owns authorization. Employee mode uses MyWeek rather than fetching colleague rows and hiding them afterward.
- UUIDs retained; logical shift IDs key assignments across versions. No slug-to-UUID guesses.
- Offset timestamps displayed in outlet timezone. Breaks, locks and multiple same-day shifts are retained. Roster metrics are provider-reported, rather than recalculated from the older prototype.
- Money is integer paise and displayed with two decimals; null coverage is distinct from zero.
- Generation uses an explicit idempotency key and base version. No automatic write retries. Polling respects provider guidance, can be cancelled and is bounded without claiming a still-running job failed.
- Results stay drafts. Nothing in the current contract preview publishes an optimizer result.

## Non-blocking provider follow-ups

1. `run.succeeded` names two candidate draft versions, while only the first has a full `schedule_version.draft` fixture. Please add a second full version fixture before testing that preview. The gateway returns an explicit missing-fixture error for its ID; it does not substitute the first roster.
2. Owner outlets list three locations, but roster fixtures cover Indiranagar only. Other permitted outlets show a missing-fixture response, not invented employees or a misleading permission denial. Add owner read fixtures for the remaining outlets for I1 preparation.
3. Some descriptions and the infeasibility summary contain mojibake punctuation. Preserve structured facts; please correct encoding in the provider generator and regenerate with a bumped manifest when ready.
4. Clarify whether explicit null on non-nullable EmployeeUpdate fields means invalid input or no change. Consumer forms will omit untouched fields; nullable preferred hours remain a separate case.
5. MyWeek has skill IDs but no skill-name mapping. The employee preview currently shows time, outlet, break and lock without inventing a role name. Please define the allowed staff skill lookup if role labels are required.

## Requests to the planning writer

Record X0.3 as done for version `2.1.0-p1p2`, with the follow-ups above. X0.1 now has the typed consumer, fixture gateway, Tailwind setup, shadcn-compatible Button primitive, dnd-kit scaffold, lint and unit/browser harness. X0.2 still needs user review and the remaining workflow surfaces. X1.1/X2.1 have fixture-driven implementations; I1/I2 remain open until real backend integration. Do not mark the complete v2 UI or release done.

Only `web/` was changed in this feature. Work is isolated in branch `codex/ui` under `.worktrees/codex-ui`; shared planning files remain with Claude.
