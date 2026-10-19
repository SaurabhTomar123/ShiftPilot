# 19 October: contract 2.3 compatibility and architecture v3

Provider commit `bd149c5` (including `97fb796` / `cd878df`) was merged into the isolated UI branch. OpenAPI types and **61 fixtures** were generated from `2.3.0-p3`; hash `43f6254a7d1b26f04658faa715dd5ed15dd9f6d174eacd3ca742a19cb1e91745`.

**Accepted for the current data/read compatibility slice.** Consumer schema tests parse all fixtures, including version revisions and the new response schemas. Employee creation/update, availability and date-specific staffing forms use the declared requests and revisions. No provider contract was hand-edited.

**P3 publication/selection approval is not granted by this slice.** The user made architecture v3 governing. Lightweight candidate selection, proposals, Published/Stale/Invalid/Changed results and template expansion need the revised contract. The legacy `draft_version_id` preview and direct-publish schemas are not evidence of completed v3 flows. See ARCHITECTURE_V3_ALIGNMENT.md. A newer provider 2.4 compatibility update is visible on Claude's branch but is not silently imported into this tested slice.

The earlier approvals below remain historical records of their declared scope.

---

# Consumer review: contract 2.2

**Approved for the declared P1?P2 UI scope**, from Claude commit `cb7c1e6` on 18 October 2026. This supersedes the 2.1 review below. Later publishing, repair and employee-request contracts remain outside this approval. Real integration gates I1/I2 remain open while the provider APIs and solver are pending.

- Generated all 49 fixtures and the TypeScript schema from `2.2.0-p1p2`; SHA-256 `0fa1b064385cf83ef41bc2c6844fb928c6241126ad3eebb7229d76422be8c16f`.
- Consumer AJV tests cover response bodies, bodyless 304 responses, and declared response headers. The suite has 71 passing unit/contract tests.
- `run_in_progress` attaches to `details.run_id`, then uses normal bounded polling. It does not submit another generation POST. Missing/malformed run IDs remain visible errors.
- Rate limiting preserves Retry-After and displays guidance without automatically retrying a write.
- Repeated week and version reads use ETags. A 304 requires a body from the same in-memory session; clearing credentials also clears cached bodies. Late responses cannot repopulate a replaced session's cache. Each read still reaches the provider for authorization; there is no global or persistent response cache.
- Owner views use the supplied Koramangala and HSR roster/employee fixtures; both candidate previews have distinct full-version fixtures. Staff role labels come from MyWeek.skills, without fetching employee costs or manager lookups.
- Explicit null updates are understood as invalid except `preferred_weekly_minutes`, where null clears the value. Future forms will omit unchanged fields.
- No shared provider contract was edited. Claude's backend work was merged into the isolated UI branch; root checkout changes were left untouched.

The five follow-ups recorded in the historical review are resolved by 2.2. Planning writer: record B0.4 consumer approval and X2.1 active-run attachment; retain fixture-driven status for X1.1/X1.3/X2.1 and keep I1/I2 open. Employee/availability/demand forms remain the next X1.2 task.

---

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
