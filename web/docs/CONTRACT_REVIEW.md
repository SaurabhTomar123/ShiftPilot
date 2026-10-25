# 25 October: direct replacement consumer review (3.19)

Frontend-only pin: **3.19.0-p4 / 118 fixtures**, provider `6c3f731a4ab50f7d924e4cf0a6d5fd213e0dc37f`, aggregate SHA-256 `71b06d910c4e214ec62720d800076abae17fa88e5dccd6365457210cfbb86bab`. Hash checks and AJV validate the snapshot; backend source/runtime remain unchanged.

Accepted: synchronous read-only recommendation POST, exact request identity, provider-ranked direct/overtime/other-outlet options, burden/cost/preference facts, rule-backed exclusions, owner-only borrowing and explicit draft preparation. The returned edit goes through revision-fenced preview and separate save before the existing proposal workflow. No inferred eligibility, automatic unlock or direct publication. Lost saves require a current draft read.

The pin has recommendation success/denial/unknown-shift fixtures but no matching replacement-edit preview/apply example. Synthetic validation rejects unsupported edits; browser mocks test the consumer save path without claiming live acceptance. Repair records now consistently choose Chitra and update their cost/trace. See [flow, validation boundaries and follow-ups](REPLACEMENT_FLOW.md).

The prior fairness fixture issue is corrected upstream at `063cf56`; this bounded 3.19 pin predates that fix and retains the warning. Scenario Lab is the next consumer slice. Historical reviews below describe their original snapshots.

---

# 24 October: portfolio, fairness and trace consumer review (3.18)

Frontend-only pin: **3.18.0-p4 / 115 fixtures**, provider `5d93779f6a51a823db9b3d376f68e9feaa22fe96`, aggregate SHA-256 `ceca5f12379c3c4d8fea346a3f5c6867edff1dc787bd0e8099f2c57519a9906e`. Per-file hashes remain verified. Backend source/runtime are unchanged; live 3.18 acceptance is pending. Earlier live checks below refer to earlier reviewed runtimes.

Accepted consumer behavior: explicit decision profiles; supplied portfolio exclusion reasons without browser ranking; engine delta reference distinct from recorded baselines; rolling fairness burden separate from weekly components/preferences; six-category trace, bounded explanations and returned provenance. Cost permissions apply inside employee reasons. Matching repair detail/select fixtures now preserve repair candidate/base identity through draft, proposal and explicit approval. Requested-record status fixtures exist but their preview-gateway integration remains separate.

Provider follow-up: `run.succeeded` gives Balanced burden 7.97, Lowest cost 7.83 and Lowest cost requested-plan fairness delta +0.02. Directions disagree. The UI warns and retains supplied values; no client correction or live-solver defect is inferred. The inconsistency also exists in reviewed upstream 3.26 fixture data. See [delivery flow and exact boundaries](DECISION_REVIEW_FLOW.md).

Newer provider replacement/Scenario Lab/P1 contracts are available upstream and await individual consumer reviews. No broad backend merge is part of this delivery.

---

# 21 October: run protection consumer review (3.15)

Frontend-only contract snapshot from provider `03d747cc0cc4b67fccaed8489abbb0d53cd741b4`: **3.15.0-p4 / 108 fixtures**, aggregate SHA-256 `0a9cd663b5817fab0013be229fe39195c9689e41ab8b15f40f445eb99d167775`. `web/contracts/v2/SOURCE.json` records byte hashes; generation verifies them. The root backend contract and runtime remain unchanged. This is not an acceptance of all newer backend features.

Accepted frontend inputs: GenerateRequest.freeze and RepairRequest.freeze (logical shift IDs, employees, local days), `409 details.frozen_logical_shift_ids`, run-confirmed IDs and the `impact` stage with release/widening reasons. Controls distinguish request preview from server scope, do not silently release pins, reject a changed repair base before writing and disclose mismatched existing-run scope. Expired candidates get explicit guidance. See [flow and verification boundaries](RUN_PROTECTION_FLOW.md).

Automatic approval review rejected the broad backend merge because of unreviewed backend files/dependencies. Only published schema/fixture data was imported into the frontend; no backend code was merged or executed. Live 3.15 solver pin-preservation, impact-quality and deployment acceptance remain pending. Prior live API evidence below refers to earlier reviewed runtimes.

---

# 21 October: v4 target and absence/repair consumer review

Architecture v4 now governs the product direction. See [v4 alignment and required handoff](ARCHITECTURE_V4_ALIGNMENT.md). Consumer pin remains 3.3.0-p4 / 83 fixtures. Remote backend 3.14 was inspected; v4 scenario/freeze/replacement routes and fairness/portfolio/decision-trace schemas are not yet declared. Endpoint examples in the architecture are not silently substituted for accepted contracts.

Absence reporting/list/status and explicit repair are integrated using the pinned types. The live synthetic API passed absence commit, automatic repair tracking, candidate detail/select, proposal creation and explicit approval; final publication had zero reported hard violations. Synthetic preview deliberately rejects requests without matching provider fixtures, including requested-record status transitions and detailed repair candidates. Plan comparison never invents fairness, a recommendation or dominance metadata. See [delivery evidence](UI_HANDOFF_V4_FOUNDATION.md).

---

# 21 October: history and restore consumer review (3.3)

Provider baseline d66ad33 (including ea13417) is merged. Generated **83 fixtures** from `3.3.0-p4`; SHA-256 `9e4961ec6a96a6e97d0d5bb659936788d7d4c47e26390776e1f22f276184dd86`.

**Accepted for listVersions, compareVersions, restoreVersion and listProposals**, plus the second candidate detail/select and acknowledged-cost fixture fixes. The consumer parses all 83 response fixtures. VersionHistory uses frozen/recorded metrics where available; missing values are stated. VersionDiff uses service-evaluated current metrics and explicit direction. Restore carries expected_base_version_id and an idempotency key; stale bases are not retried automatically. The returned draft is reviewed against current validation and enters proposals. No direct legacy publication call is added.

The previous candidate-detail and acknowledged-cost follow-ups are resolved: the second option is now reviewable/selectable, and accepted changed cost is stored/displayed after publication. Proposal discovery is integrated in History, with getProposal and a fresh version read before resuming its review. The API independently owns authorization and expiry.

The isolated real API passed history GET, compare GET, restore POST (201), proposal creation (201), proposal listing and reopening a proposal/version (200). Restore left the published pointer unchanged. See UI_HANDOFF_HISTORY.md for the synthetic database setup and test boundaries. No claim of complete cross-tenant, deployment or release acceptance is made.

Provider 3.11 is available upstream. This slice deliberately pins 3.3; later template/import/notification APIs and the 3.5 replay guarantee remain to be reviewed and integrated. Earlier requests for those features are historical, not a claim that Claude has not delivered them.

---

# 19 October: manual draft edit consumer review (3.1)

**Accepted for createDraft, previewEdits and applyEdits request/response shapes.** Provider version and hash remain 3.1.0-p4 / `7b7128bc86e8747a95e92bb6048dacb1afc53c227fb08345aeb3c22eb7ebe763`. Request examples are generated from provider fixture metadata; response records and backend source were not edited.

The UI sends the reviewed expected_revision and edits unchanged. Omitted update fields remain untouched; explicit null unassigns a teammate. Local time conversion preserves unchanged ambiguous instants and rejects newly chosen skipped/repeated clock times. Preview is non-mutating; only an apply response replaces accepted draft data. Hard-invalid previews cannot be applied through this UI. Revision or input changes invalidate the prior preview.

Provider follow-up: applyEdits/discardDraft do not declare or implement idempotent replay, despite the broader v3 mutating-request convention. The SDK sends an Idempotency-Key on apply, but the consumer makes no replay guarantee. A save error pauses editing and requires reload; this was checked against an actual committed save whose response was replaced with 503 in the browser bridge. Please align the provider convention in a future contract revision. Preview POST is read-only and does not need replay handling.

The isolated real API passed create/resume draft, preview lock, apply lock (revision 2), preview/apply unlock and reload after a lost success response (revision 3). The published pointer stayed unchanged. Additional real API previews for unassignment, role change, move and removal returned their typed changes and hard violations without changing revision or assignments. General assignment creation is not exposed until template selection is contracted; the legacy AddShift shape alone does not provide a v3 template picker.

Earlier review entries below describe previous slices.

---

# 19 October: contract 3.1 candidate and proposal review

Provider `f8837ae` (including `38899e3`, `c5a7a38`, `87ac6e7`) is merged. Generated all **78 fixtures** from `3.1.0-p4`; SHA-256 `7b7128bc86e8747a95e92bb6048dacb1afc53c227fb08345aeb3c22eb7ebe763`.

**Accepted for candidate reads, explicit selection, proposal create/get/approve/reject, stored metric fields and revalidated version caching.** Candidate reads never fetch a pre-created draft. Selection returns a real draft only after POST, with an explicit stable idempotency key. Proposal creation sends the reviewed draft revision. Every 200 approval is inspected for its outcome; Stale and Invalid cannot produce a success state. Changed renders typed before/after deltas, requires acknowledgment and sends a distinct approval action. Transport failure retains the action key for an explicit retry. No direct legacy publication call is used.

All response fixtures pass consumer AJV schema/header validation. A real API/worker check against the isolated Codex database passed generation (202), read-only candidate detail (200), selection (201), proposal creation (201), approval (200 Published), and week readback (71 shifts, zero reported hard violations). Draft count stayed zero between generation and selection. This is not a claim that deployment/CORS, tenant gates or all v3 features passed.

Provider follow-ups: only the Balanced candidate has a detail/select fixture, so the synthetic UI explicitly refuses to fabricate the second candidate's diff. Also, `proposal.approve.acknowledged` retains the original recorded labour cost (7,470,000 paise), while `proposal.approve.changed` reports a move to 7,843,500. The preview preserves the provider's published summary rather than inventing a corrected amount; please align that fixture story. The real Published smoke did not exercise a changed cost. Neither follow-up blocks the reviewed request/outcome shapes.

Earlier reviews below are historical and describe earlier deliveries, not the current contract pin.

---

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
