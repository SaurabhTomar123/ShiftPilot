# ShiftPilot scheduling UI

Codex owns this frontend; Claude owns database/backend delivery. The main UI now consumes contract **2.2.0-p1p2** rather than the original local prototype shapes.

## Run

```powershell
cd web
npm ci
npm run dev
```

Open http://127.0.0.1:3001. This port isolates UI work from the main checkout. Node 24 is supported; dependencies are locked and the Geist font is self-hosted.

## Two explicit environments

- `/`: synthetic provider-contract preview. Uses the supplied 49 fixtures, UUIDs, skills, breaks, locks, exact money, published metrics and asynchronous run statuses. Manager, owner and employee personas have separate session/view state. Try generation on 26 October; use the demo outcome selector for feasible, infeasible, timeout, worker failure, stale, denied, existing-run and rate-limit states. Draft preview is read-only; there is no publication endpoint in this slice.
- `/sandbox`: the earlier browser-local editing prototype, with 60 synthetic employees across three outlets, shift editing, dnd-kit drag to empty same-role cells, locks, sample generation, simple absence replacement and local publish/history snapshots. It remains separate from the contract dataset and retains its localStorage key.

The provider fixtures now include 13 employees per outlet across all three owner outlets, plus both candidate drafts. This is still synthetic data, not the final ~60-person database seed. Unsupported weeks and requests return an explicit missing-fixture error.

**No live backend or solver is claimed.** The default same-origin gateway serves synthetic fixtures only. Real provider routes currently return 501 until their implementation lands. Editing/repair/publication in the sandbox are local simulations, not validated operational writes.

## Frontend foundation

Next.js 16, React 19, strict TypeScript, Tailwind 4 (utilities/theme without a reset of the established CSS), a shadcn-compatible Radix Slot/Button primitive, Phosphor icons and dnd-kit. ESLint covers TypeScript, React hooks and JSX accessibility; Vitest covers the client and provider schemas. Native dialogs support focus management and Escape. Keyboard Enter opens the sandbox shift editor; Space starts a drag, Escape cancels. Full reassignment/resize and server validation belong to X3.1.

## Contracts and checks

```powershell
npm run contracts:generate
npm run contracts:check
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
```

The generator reads `../contracts/v2` and writes only `src/api/generated`. Its manifest includes the schema/index/fixture hash. Drift checks fail when provider files change. The JavaScript/AJV suite independently validates every response fixture. Browser tests use installed Chrome at desktop/mobile sizes and include automated WCAG A/AA scans; they do not replace manual assistive-technology testing. Captures are gitignored under `.impeccable/review/`.

For production-browser checks, build first and set `PLAYWRIGHT_SERVER_MODE=production`. The runner launches Next directly. If a restricted Windows shell blocks child-process cleanup, run the server in a separate terminal first; Playwright reuses it and leaves its lifecycle with that terminal.

## Live API connection, when ready

Set `NEXT_PUBLIC_API_BASE_URL` to the API origin in an untracked `.env.local`, then restart Next.js. Only a public origin belongs there: never database URLs or admin/provider secrets. The same SDK sends bearer headers and keeps credentials in memory; fixture scenario headers are confined to `/api/fixture`. Demo sign-in is supported by this contract; private deployments need their future real sign-in flow.

No fallback to fixtures occurs after a real API error. Live mode surfaces 401/403/409/501 honestly. Publication and other future writes cannot be enabled until their contracts exist.

## Handoffs

- [Consumer approval and provider follow-ups](docs/CONTRACT_REVIEW.md)
- [Initial backend handoff](docs/BACKEND_HANDOFF.md)
- [Initial workflows and wireframes](docs/WORKFLOWS.md)
- [Design system](DESIGN.md)

Detailed employee/skill/availability and demand forms, employee requests, import, rule parsing, repair and durable publication remain subsequent slices. Review the current task board; the earlier workflow note records the first prototype, not current completion of every UI task.

Design references: [Taste Skill minimalist UI](https://github.com/Leonxlnx/taste-skill/blob/main/skills/minimalist-skill/SKILL.md), adapted to an operational roster, and [Superdesign reference](https://p.superdesign.dev/draft/60a3db55-605b-483b-b5c6-a5ebb9c9d902).

Read caching is scoped to an in-memory client session and only covers schedule weeks and versions. Repeated reads send `If-None-Match`; a 304 reuses that session's previous body. Requests still reach the provider for authorization. Persona replacement and 401 clear cached bodies as well as credentials. For a cross-origin API, the provider must expose ETag and Retry-After through CORS for these headers to be readable.
