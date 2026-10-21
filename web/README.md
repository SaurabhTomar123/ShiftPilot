# ShiftPilot web

Codex owns `web/`; Claude owns backend/database contracts. **Architecture v4 is governing.** See [v4 alignment and delivery order](docs/ARCHITECTURE_V4_ALIGNMENT.md). This branch currently consumes provider contract **3.3.0-p4**. Candidate review/selection, manual draft edits, history/restore and proposal approval now use the v3 contract; absence reporting and repair review are connected as well. Staffing templates remain an upcoming integration.

## Run

```powershell
cd web
npm ci
npm run dev
```

Open http://127.0.0.1:3001. The UI uses Next.js 16, React 19, TypeScript, TanStack Query, Tailwind 4, Phosphor, a Radix/shadcn-compatible Button and dnd-kit. Fonts are bundled locally.

## Current surfaces

- `/`: provider fixture preview, with separate owner/manager/employee sessions. Use Schedule, Employees, Staffing, Repair Inbox and History navigation. Employee/skill/availability and date-specific staffing forms have validation, explicit save results and stale-edit recovery. Synthetic edits exist only in a bounded, expiring preview session. Persona changes/server restarts reset them; fixed roster/solver fixtures do not change with input edits.
- Manual drafts: copy the published week, choose an assignment, change its teammate/role/time or lock state, preview server validation, then apply the reviewed request. Removing an assignment also requires preview. Input changes invalidate the preview. Stale or uncertain saves require explicit reload; they never retry automatically. The synthetic preview supports the opening-cook lock and conflicting-reassignment examples only.
- History: inspect recorded version metrics, compare assignments in either direction, restore an older version into a newly validated draft, and discover pending proposals. Restored drafts enter proposal approval; no restore publishes directly.
- Repair Inbox: list records by outlet/week, save a confirmed absence or request, explicitly confirm/reject/cancel records, track automatic repair runs, authorize individual locked assignments, and review widening stages and replacement options. Selection creates a draft that uses proposal approval. Synthetic mode supports only the supplied reporting and repair-summary examples; detailed repair review and other status writes require the live API. See [absence flow](docs/ABSENCE_FLOW.md).
- Plan Compare: compare returned alternatives side by side, with labelled recorded-baseline deltas for coverage/cost/overtime. Missing fairness burden remains explicitly unreported; the UI does not infer portfolio dominance or rename preference match as fairness.
- Appearance: three type treatments, three palettes, and slide/dissolve/fold sidebar transitions. Desktop collapses to a labelled icon rail; mobile has Escape, focus restoration, a backdrop and reduced-motion support.
- `/sandbox`: earlier local editing/dragging/repair/publication prototype. Its browser-local data and Geist palette remain separate.

The generated registry has 83 provider fixtures, 13 employees per outlet and two detailed candidate options. History comparison fixtures cover versions 3/4 and the restore story uses version 2; unsupported synthetic requests return an explicit missing-fixture message. Balanced selection creates a synthetic draft; proposal approval can demonstrate Published, Stale, Invalid and Changed, with explicit metric acknowledgment. Synthetic publication updates this preview session only. The real seed has 60 employees across three outlets. Unsupported fixture requests return an explicit error. No default UI action publishes a real schedule.

## Checks

```powershell
npm run contracts:generate
npm run contracts:check
npm run typecheck
npm run lint
npm test
npm run build
npm run test:e2e
```

The generator reads `../contracts/v2`; do not edit generated files. AJV checks provider response schemas, headers and bodyless 304s. Browser checks cover desktop/mobile flows and axe scans. Captures under `.impeccable/review/` are local and ignored. For production browser checks, build first and set `PLAYWRIGHT_SERVER_MODE=production`, or start a separate production server for Playwright to reuse. Stop that production server before rebuilding it.

## API mode

Set `NEXT_PUBLIC_API_BASE_URL` to the API origin in an untracked `.env.local`, then restart Next (rebuild for production). Only a public origin belongs there. No database URL, admin credential or provider key belongs in frontend environment variables.

The client uses an in-memory bearer token and a session-local TanStack Query cache. Persona change/401 clears cached data and credentials, and cancels requests. Writes invalidate reads; GETs are not automatically retried. Week/version reads revalidate ETags and accept 304 only with a body from the same session. The transport does not trust immutable lifecycle-status caching, matching architecture v3. Cross-origin APIs must expose ETag and Retry-After.

Fixture scenario/session headers are never sent to a configured real API. There is no automatic fallback to fixtures after an API error. Dedicated API/database smoke checks are described in the current handoff; they do not switch the default preview to live mode or close the v3 integration gates.

## Architecture and handoffs

- [V4 Repair Inbox / plan comparison handoff](docs/UI_HANDOFF_V4_FOUNDATION.md)
- [Architecture v4 alignment and delivery order](docs/ARCHITECTURE_V4_ALIGNMENT.md)
- [Historical architecture v3 alignment](docs/ARCHITECTURE_V3_ALIGNMENT.md)
- [Previous history/restore handoff](docs/UI_HANDOFF_HISTORY.md)
- [Previous manual-edit handoff](docs/UI_HANDOFF_MANUAL_EDITS.md)
- [Previous v3 review handoff](docs/UI_HANDOFF_V3_REVIEW.md)
- [Previous forms/design delivery](docs/UI_HANDOFF_2026-10-19.md)
- [Design system](DESIGN.md)
- [Contract reviews](docs/CONTRACT_REVIEW.md)

Upcoming P0 work follows v4: impact-aware freezes and pins, engine-selected portfolios, historical fairness burden, decision traces, replacement recommendations, then isolated Scenario Lab and current-fact conversion. Existing template/import/rules integrations and P1 demand/employee workflows follow the contract handoff. The old sandbox is not evidence that those server workflows are delivered.

Design skills are local development tools, not runtime dependencies. Current work uses the requested [taste redesign guidance](https://github.com/Leonxlnx/taste-skill/tree/main/skills/redesign-skill), [frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design), and [UI/UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill). [improve-animations](https://github.com/emilkowalski/skills/tree/main/skills/improve-animations) supplies read-only audit/planning criteria; implementation remains the authorized repository task.

This UI slice deliberately pins reviewed contract 3.3. Provider 3.14 is available upstream; its later v3 APIs and the new v4 engine features are separate integration milestones. Template, replay, CSV, staff self-service, notification and retention integrations are not claimed by this delivery. In particular, apply-edits recovery still uses the reviewed revision-only behavior; the newer replay guarantee arrives with the later contract upgrade.
