# Scheduling UI workflows and first-slice handoff

18 October 2026. Product references: `docs/SCHEDULING_V2_SPEC.md`, roadmap decisions and `SCHEDULING_V2_TASKS.md`. This is a UI work record for Claude, the current shared-planning writer; it does not change task-board states directly.

## Task state request

| Task | Requested state | Evidence / remaining work |
|---|---|---|
| X0.1 | in_progress | Next.js/React/strict TypeScript, self-hosted Geist, Phosphor icons, dependency lock, build and Playwright/axe scaffolding implemented. Typecheck/build and 12 desktop/mobile checks pass. Current prototype uses custom CSS and native drag; Tailwind/shadcn/dnd-kit, lint/unit harness and the contract-backed mock adapter are not yet delivered. |
| X0.2 | review, partial | Manager desktop/mobile prototype, flows below and token-bearing `web/DESIGN.md` available. No user design approval is claimed. Owner/employee screens and server failure states need their subsequent implementation. |
| X0.3 | blocked: B0.3 | No `contracts/v2/` exists at this handoff. Local fixture view models are not an API proposal or contract approval. |

The prototype was started before the new task board landed. Shared planning/spec changes discovered during the session were preserved. Generated design context is contained under `web/`; no backend source or shared contract was edited. The user authorized pushing this first UI feature to the existing repository. See Git history for its feature commit. Isolate subsequent concurrent implementation in a UI branch/worktree; do not move Claude's changes.

## Desktop composition

```text
┌──────────────┬─────────────────────────────────────────────────────────┐
│ Workspace    │ Schedule                         Synthetic browser demo │
│ Schedule     ├─────────────────────────────────────────────────────────┤
│ Team         │ Weekly schedule                     Outlet selector     │
│ Demand       │ Draft metrics and publication state                     │
│ Requests     │ Week controls              Export / Generate / Publish  │
│ Rules        ├──────────────────────────────────┬──────────────────────┤
│ History      │ Employee / role filters          │ Coverage to review   │
│              │ Employee × seven-day roster      │ Locks and requests   │
│ Help         │ Shift editor / preview dialog    │ Try absence workflow │
│ Settings     │ Legend and local-save status     │                      │
└──────────────┴──────────────────────────────────┴──────────────────────┘
```

## Mobile composition

```text
Navigation / Schedule / Synthetic browser demo
Heading / outlet selector
Draft metrics / publication state
Week controls / generate / publish
Filters
Sticky employee column + horizontally scrollable days
Coverage note / absence entry point
Dinner targets / demo limitations
```

Current dialogs trap focus via native `<dialog>`, support Escape, and restore focus. Editing a shift does not require dragging. Full keyboard reassignment and touch drag/resize still belong to X3.1; do not mark it complete based on the prototype.

## User journeys

**Manager planning:** choose authorized outlet/week -> load roster/data -> generate a candidate -> review authoritative metrics and typed diff -> edit if needed -> validate preview -> explicitly publish. Pending changes remain drafts. Prototype generation/publication uses labelled fixtures and local snapshots only.

**Manager absence:** report absence -> resolve a lock conflict explicitly if applicable -> request repair -> compare available strategies and reasons -> review changed assignments -> approve -> observe durable publication result. An absence is an operational fact even when no repair exists. The prototype only explores an unlocked assignment and same-role/day replacement; it does not implement that production lifecycle.

**Owner:** organization-scoped outlet selector -> review outlet roster/needs -> inspect authorized cross-outlet proposals -> compare affected outlet versions -> approve atomic publication. Do not expose a manager-only screen as permission enforcement. The production owner surface awaits backend capability contracts.

**Employee:** own-week view -> select unavailable interval or leave/swap request -> review the request -> submit -> view pending/approved/rejected status. No access to colleague costs, approval controls or direct solver execution. This surface is planned, not implemented.

**History:** select week/outlet -> inspect immutable version and actor/reason -> compare -> preview restore against current facts -> publish a new version. The prototype stores snapshots and loads them into a local draft; it does not revalidate availability.

**Rule:** form or natural-language shortcut -> supported structured rule -> clarify ambiguous employees/dates/scope -> preview affected employees -> explicitly save -> regenerate/repair a draft. The current rule form stores text-only configuration previews; it does not parse or enforce text.

**CSV onboarding:** select file -> preview/redact sample -> confirm mappings -> inspect row errors and resolve date ambiguity -> explicitly commit -> show durable result/recovery. Not yet implemented; backend contract requested in BACKEND_HANDOFF.md.

## State vocabulary for integration

| State | UI behavior |
|---|---|
| Loading | Preserve page structure; show roster skeleton and disable dependent writes. |
| Empty | Explain absent data and offer the appropriate create/generate action. |
| Draft/pending | Label preview; keep published facts separate; do not imply employee notification. |
| Validation failure | Show structured issues beside affected assignments and explain recovery. |
| Denied | State the scoped access problem; avoid retaining the previous outlet/persona's data. |
| Stale | Preserve intended edit as a preview; refetch current version and ask for review. Never blindly retry a publication. |
| Infeasible | Show supported diagnostics/authorized relaxations; do not call a timeout impossible. |
| Unknown/timeout | Keep durable run ID and status recovery; never imply no changes after an ambiguous write. |
| Published | Show authoritative version/status independent of explanation availability. |
| Storage unavailable (demo) | Explicitly say that edits are session-only. |

Only loading, empty, local draft/publication and browser-storage failure are currently implemented. Production denied/stale/solver outcomes must be driven by B0.3 fixtures and real API results.

## Verification handoff

- `npm run typecheck`: passed.
- `npm run build`: passed; static `/` and not-found routes generated.
- `npm run test:e2e`: 12 passed in the final desktop/mobile run, including automated roster WCAG A/AA checks. Captures are in `web/.impeccable/review/` (gitignored).
- Separate screenshot review found two presentation issues; both were resolved and confirmed in the verdict pass. This is not certification of the entire future UI or backend.
- Impeccable engine/context tooling was unavailable due to its cache location. Context was read directly; no detector/concept-tool pass is claimed.
- Taste Skill's minimalist guidance and a Superdesign reference informed the implementation. No user design approval or pixel-fidelity claim is recorded.

Next action: Claude supplies B0.3 provider schemas/fixtures; Codex reviews them, finishes the X0.1 harness and adapter, then replaces local view models through typed mapping. Do not expose the existing v1 reset or payroll/chat API to this UI.
