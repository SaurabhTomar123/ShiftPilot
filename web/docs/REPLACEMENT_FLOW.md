# Find cover: direct replacement review

25 October 2026. Historical replacement slice: the consumer has since moved to 3.20 for Scenario Lab. Provider 3.27 now supplies the requested replacement-edit records; consuming that newer slice remains a follow-up. Architecture v4 governs; Codex owns the UI and Claude owns API, database and scheduling implementation.

## Accepted contract slice

Frontend-only snapshot **3.19.0-p4 / 118 fixtures** from provider `6c3f731a4ab50f7d924e4cf0a6d5fd213e0dc37f`. Aggregate SHA-256: `71b06d910c4e214ec62720d800076abae17fa88e5dccd6365457210cfbb86bab`. Source bytes/hashes remain in `web/contracts/v2/SOURCE.json`. No backend source, dependency, migration, worker or database change is included.

This slice adds `POST /v2/recommendations/replacements`: a synchronous read-only recommendation call despite its HTTP method. No idempotency key, automatic retry, assignment save, absence write or publication accompanies the lookup. The provider requires publication permission; only owners can include other outlets. The browser preserves provider ranking and eligibility, rather than deriving either from roster data.

## User flow and safety

1. In Schedule or Repair Inbox, open Find cover for a shift. Select the published/draft assignment and priorities. An affected shift is preselected when a saved absence provides one. No lookup runs on entry.
2. Find cover shows qualified/eligible counts, the returned top options, policy and recorded rule-backed exclusions. Direct cover means the rest of the roster stays fixed. People blocked by another shift may need a repair run; the UI does not treat them as direct alternatives.
3. Inspect engine rank, direct/overtime/other-outlet disruption, exact-paise cost against leaving the shift open, overtime minutes, historical fairness change, weekly hours and preferred-window status. Missing fairness is unreported; a null preferred window means not specified. Cost permissions apply inside detailed reasons as well as metrics. Rule/absence IDs appear only when supplied.
4. Review a person in draft checks the latest published base or the current draft revision. For a published version, it explicitly creates a copy with a stable creation key, then submits the provider's returned update edit to validation. The logical shift, assignee, times, skill, draft identity and lock state must still match. Locks require separate draft-editor review; no automatic unlocking occurs.
5. Validation errors preserve the prepared draft. A hard violation blocks saving. Save replacement to draft sends the exact reviewed edit and revision once. It opens the existing draft/proposal review; no recommendation action publishes. Uncertain saves clear the actionable preview and require a current draft read before further work, matching the conservative existing editor behavior.

Changing lookup inputs clears old results. Version, outlet, week, persona or screen changes cancel obsolete waits. Recommendation identity must match the requested version, shift and profile. Closing retains any already created draft and returns focus to the trigger. The panel is usable on phones and with a keyboard.

## Preview and verification boundaries

The supplied success fixture is Ravi Kumar's Prep assignment on 21 October at Indiranagar, Balanced with limit 5. Chitra Indiranagar and Aman Shah are returned in that order. The provider also supplies manager borrowing denial and unknown-shift validation. Unsupported dates, profiles, limits, draft versions and owner widening remain explicit errors; the gateway does not rename the fixed Balanced result.

The provider has not supplied matching replacement-specific edit-preview/apply fixtures in this pin. The preview can prepare a manual draft, but validation of the returned replacement edit fails explicitly. No fabricated replacement save or solver validation is displayed. The retained draft can be opened for review. Existing generic edit fixtures cover other edits and are not substituted for this replacement.

Browser tests use clearly local mocked validation/apply responses to verify exact request/revision, separate save/proposal, hard-invalid behavior and lost-response recovery. Those checks are consumer behavior evidence, not live API/solver acceptance. Other checks use the unchanged provider recommendation fixtures, including cost redaction, empty/locked/mismatched results, late responses, accessibility and phone overflow. Earlier real API acceptance remains evidence for the reviewed 3.3 runtime only. Live 3.19 replacement, cross-tenant, worker and release acceptance remain open.

Verified for this slice: 179 unit/contract tests, all 24 replacement desktop/phone checks, contract hashes, lint and production build. The full shared browser regression is checked before the feature push.

## Provider follow-ups and next UI work

- Add matching replacement-edit preview/apply records for the published recommendation and a direct-cover story through draft/proposal validation. Include stale base/revision and lock/conflict examples. Existing provider endpoints are already consumed; this request concerns synthetic coverage and live acceptance.
- Provider `063cf56` has corrected the previous fairness trace inconsistency upstream. This focused 3.19 snapshot predates that correction, so its old generation fixture still triggers the consistency warning. Accept the fix with a later reviewed snapshot; do not modify provider fixture bytes locally.
- The 3.19 repair fixtures also change their chosen replacement from Aman to Chitra and adjust cost/trace consistently. Consumer tests use the returned identities rather than hard-coded names.
- Next P0 consumer work is Scenario Lab: isolated events, run/compare and current-fact conversion through the normal approval workflow. Those contracts are published in newer revisions and need a separate bounded review.
