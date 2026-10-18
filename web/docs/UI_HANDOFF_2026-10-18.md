# UI foundation and contract consumer handoff

Task: X0.1, X0.3; fixture-driven portions of X1.1, X1.3 and X2.1.

Branch: `codex/ui`, based on `a4d6f0e`. Changed area: `web/` only. No migrations, seed/reset operations, backend files or shared planning files changed.

## Delivered

- X0.1 foundation: locked Next/React/TypeScript, Tailwind, shadcn-compatible Button, dnd-kit scaffold, ESLint, Vitest, Playwright/axe and a generated contract fixture layer. Clean install verified. Existing sandbox retained at `/sandbox`.
- X0.3 approved contract **2.1.0-p1p2** for its P1–P2 scope, recorded in CONTRACT_REVIEW.md. Independent AJV validation covers all **39** provider fixtures; generation/drift checks bind generated types/data to provider source hashes.
- Main `/` displays provider UUIDs, skills, breaks, locks, employee rows and authoritative fixture metrics. It preserves multiple same-day assignments and distinguishes draft preview from published version.
- Manager/owner/employee session views with memory-only credentials, capability-driven controls, abort/clear on scope changes, and 401 recovery. Employee data comes from MyWeek, not a filtered management roster.
- Generate -> bounded read-only polling -> terminal result -> candidate preview. OPTIMAL, FEASIBLE, INFEASIBLE, UNKNOWN and worker failure have distinct explanations. Stale writes require review/reload; writes are not retried automatically.

## Verification

- `npm ci`: clean install passed, zero reported vulnerabilities.
- `npm run contracts:check`: 39 fixtures verified for 2.1.0-p1p2.
- `npm run lint`: passed, no warnings.
- `npm run typecheck`: passed, including route generation for clean-checkout use.
- `npm test`: 57 tests passed (all provider response schemas plus client/polling/presentation cases).
- `npm run build`: passed; `/`, `/sandbox` and the dynamic fixture gateway built.
- `PLAYWRIGHT_SERVER_MODE=production npm run test:e2e`: 28 desktop/mobile checks passed against the production build, including automated roster WCAG A/AA scans and the preserved sandbox flows.
- Windows runner follow-up: the initial managed npm-wrapper server required explicit shutdown after its 28 tests. The config now launches Next directly; an isolated production browser smoke completed and shut its server down cleanly with process-cleanup permission. In restricted environments, start the server separately and let Playwright reuse it if child-process cleanup is blocked.
- Separate visual reviewer: ship at the scope of the published-roster desktop/mobile captures; no material fixes required. This is not approval of uncaptured future screens, live integration, or the entire MVP.

## Consumer actions and limits

Claude, as planning writer: record X0.3 approval and X0.1 foundation evidence, and review the non-blocking provider follow-ups in CONTRACT_REVIEW.md. X0.2 remains partial/review; do not infer user design approval from this implementation. I1/I2 remain open until the real APIs run successfully.

The contract fixture dataset contains 13 Indiranagar employees; it is not the final 60-person seed. The second candidate's full draft and other owner outlet rosters need provider fixtures. Unsupported fixture calls return explicit 501 errors. Main-route generation does not invoke the real solver or publish anything. The sandbox's writes remain browser-local simulations.

Next UI work: typed employee/skills/availability/demand forms against this approved contract, then real roster-read integration when B1.2/B1.3 land. Keep publication/repair/rules/import controls out of the contract preview until their provider contracts exist.
