# UI handoff: contract 2.2

Consumer approval of Claude commit `cb7c1e6`: see CONTRACT_REVIEW.md. Delivered in the isolated `codex/ui` worktree; the user's dirty root docs branch was not changed.

## Delivered

- Generated OpenAPI types and all 49 fixtures for `2.2.0-p1p2`.
- Existing generation run attachment on 409 `run_in_progress`, without a duplicate generation write.
- Retry-After guidance on 429; no automatic write retry.
- Session-local ETag revalidation for schedule weeks and versions, including bodyless 304. Session replacement/401 clear cached data. Late old-session responses are rejected.
- Owner roster/employee fixture reads for all three locations, distinct previews for both candidates, employee skill labels from MyWeek.skills.
- Fixture response headers are preserved and consumer tests check their OpenAPI declarations.

## Validation

`npm run typecheck`, `npm run lint`, `npm test` (71 passing), `npm run build`, and `npm run contracts:check` (49 fixtures) passed. Browser run: 30 passed initially, with two rate-limit assertions failing because they also selected Next's hidden route announcer. Scoped those assertions to main; both desktop/mobile reruns passed. All 32 browser cases passed across the full run and focused rerun. Axe checks and viewport overflow checks passed on desktop/mobile; existing roster screenshots inspected.

Preview remains http://127.0.0.1:3001. Data and optimizer outcomes remain synthetic fixtures. Real B1.2/B1.3 data, solver and integration gates I1/I2 are still pending. No publish, repair or backend persistence is claimed.

## Next

X1.2 employee/skill/availability/demand forms are ready against the approved contracts. They have not been implemented in this slice. Later edit/publication/repair/request flows still require their contracts from Claude. Planning writer should record B0.4 approval and the X2.1 attachment change, retaining the integration caveats.
