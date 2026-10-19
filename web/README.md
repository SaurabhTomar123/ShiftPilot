# ShiftPilot web

Codex owns `web/`; Claude owns backend/database contracts. **Architecture v3 is governing.** This branch currently consumes provider contract **2.3.0-p3** for tested data/roster compatibility. The revised candidate/proposal/template contracts must be reviewed before those v3 flows are connected.

## Run

```powershell
cd web
npm ci
npm run dev
```

Open http://127.0.0.1:3001. The UI uses Next.js 16, React 19, TypeScript, TanStack Query, Tailwind 4, Phosphor, a Radix/shadcn-compatible Button and dnd-kit. Fonts are bundled locally.

## Current surfaces

- `/`: provider fixture preview, with separate owner/manager/employee sessions. Use Schedule, Employees and Staffing navigation. Employee/skill/availability and date-specific staffing forms have validation, explicit save results and stale-edit recovery. Synthetic edits exist only in a bounded, expiring preview session. Persona changes/server restarts reset them; fixed roster/solver fixtures do not change with input edits.
- Appearance: three type treatments, three palettes, and slide/dissolve/fold sidebar transitions. Desktop collapses to a labelled icon rail; mobile has Escape, focus restoration, a backdrop and reduced-motion support.
- `/sandbox`: earlier local editing/dragging/repair/publication prototype. Its browser-local data and Geist palette remain separate.

The generated registry has 61 approved-provider fixtures, 13 employees per outlet and two candidate drafts. The real seed has 60 employees across three outlets. Unsupported fixture requests return an explicit error. No default UI action publishes a real schedule.

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

- [Architecture v3 alignment](docs/ARCHITECTURE_V3_ALIGNMENT.md)
- [Current delivery handoff](docs/UI_HANDOFF_2026-10-19.md)
- [Design system](DESIGN.md)
- [Contract reviews](docs/CONTRACT_REVIEW.md)

Upcoming work follows v3: staffing templates and preserved manual overrides, lightweight candidate selection, proposals with Published/Stale/Invalid/Changed outcomes, absence-triggered repair, fixed-template CSV onboarding, rules, history and validated restore. The old sandbox is not evidence that those server workflows are delivered.

Design skills are local development tools, not runtime dependencies. Current work uses the requested [taste redesign guidance](https://github.com/Leonxlnx/taste-skill/tree/main/skills/redesign-skill), [frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design), and [UI/UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill). [improve-animations](https://github.com/emilkowalski/skills/tree/main/skills/improve-animations) supplies read-only audit/planning criteria; implementation remains the authorized repository task.
