# Current contract workspace design

The new working-document experiment in `DESIGN.md` supersedes the previous green/Geist treatment recorded below. The default is Ink + Workshop (IBM Plex Sans working text, Bricolage headings). Appearance exposes Paprika/Olive, Fraunces/Plain, and slide/dissolve/fold choices. Desktop gets a named icon rail; mobile gets inert closed content, focus management, Escape, backdrop closing and reduced-motion support.

This delivery also adds real employee/skills/availability and date-specific staffing forms, session-local synthetic editing, typed API writes and TanStack Query. The forms are not a staffing-template expansion or v3 publication implementation. See the architecture alignment and 19 October handoff for exact boundaries.

The requested additional skills were installed and inspected: `improve-animations` (read-only audit/planning criteria), `frontend-design` (intentional typography/color choices), and `ui-ux-pro-max` (verified focus-visibility and cancellable-transition search results). These are development tools, not frontend runtime dependencies. They will be discovered automatically on the next turn.

---

Historical design extension follows; numerical measurements below describe the previous version.

# Contract workspace design

Updated 18 October 2026 in response to the user's request for the full taste-skill package, more vibrancy and more useful detail. Canonical tokens and layout are in `web/DESIGN.md`; the preview sidecar and Superdesign notes reflect this direction. Earlier minimal UI measurements in prior handoffs are historical.

## Package and scope

All 14 skill directories in Leonxlnx/taste-skill were installed to the user's Codex skills directory using the skill-installer helper. The installed package will be auto-discoverable next turn; the relevant SKILL.md files were read directly for this implementation. Applied `redesign-existing-projects` guidance: scan, diagnose, then improve the existing stack and preserve working behavior. The default v2 skill explicitly excludes dashboards/app screens, so marketing photography, randomized heroes and cinematic scrolling were not added. Installing the package does not mean simultaneously applying its contradictory minimalist, brutalist and marketing directions.

Source: https://github.com/Leonxlnx/taste-skill, especially skills/redesign-skill/SKILL.md and the default skill's documented scope.

## Implemented

- Deep green identity/navigation frame, teal actions, light blue-gray canvas and five distinct skill colors with written labels.
- Larger shift times and role labels. Break duration and locked status are visible before expanding; native details retain break start, lock reason and confirmed absence explanations.
- Published, draft and empty-week status ribbons with explanatory copy. Published demo has a direct Plan upcoming week action.
- Week facts: employees, shifts, locked assignments and timezone. These describe the full version, independent of row filters.
- Explanatory preferred coverage, assigned time, estimated cost and minimum staffing metrics. Native coverage meter retains a written value. Costs remain capability-gated.
- Skill filters with aria-pressed state, combined name search and a written no-results state. They filter teammates by their skills, preserving each displayed shift's actual role.
- Staffing review uses provider coverage cells, reports preferred staff-minute deficits and preference match, and shows four gaps with minimum deficits prioritized. Staff-minutes and minimum versus preferred targets are explained.
- Draft employee hours come from displayed assignments minus their unpaid breaks and are labelled as hours in that draft. Published row hours remain the provider's total across all outlets; these scopes are not interchangeable.
- Employee view retains own assignments, skill, break and lock information without fetching colleague costs or showing manager planning instructions.

## Boundaries

The root remains a synthetic contract 2.2 preview, not a real solve or publication workflow. All permission, stale, timeout, active-run attachment, cache/session and idempotency behavior is preserved. `/sandbox` retains its earlier local editing prototype and neutral palette. The user's dirty root worktree and Claude's backend files were not edited.

## Verification

Type check, lint, 71 unit/contract tests and production build passed. The complete desktop/mobile browser suite passed all 36 cases, including axe contrast checks, metric explanations, skill/name filtering, plan-week navigation, generation/preview, role privacy, errors and the sandbox regression suite. Captured and inspected 1600px, 768px and 390px layouts with no page overflow. The final draft-hour correction received a focused generation-preview rerun after rebuilding.

The first pass caught an ambiguous Next week shortcut name and low avatar-initial contrast; both were fixed in the batch. Design checks establish only the tested fixture states and viewports, not user design approval or universal accessibility conformance.
