# ShiftPilot scheduling UI

Next.js 16 / React 19 / strict TypeScript. This replaces the retired chat UI plan. Codex owns the whole UI; Claude owns backend/database delivery.

## Run

```powershell
cd web
npm ci
npm run dev
```

Open http://127.0.0.1:3000. Node 24 was used during setup. Dependencies are locked; fonts are self-hosted.

## Current slice

- Weekly roster, three outlets and 60 synthetic employees; search, role filters, week selection and CSV export.
- Shift add/edit/remove, locks and desktop drag to an empty same-role employee/day cell.
- Sample-week generation preserving existing locks, using fixtures rather than a solver.
- Absence/replacement preview using simple role/day fixture filtering.
- Local publication, reload recovery, version history and restore-as-draft.
- Team list/add form, editable kitchen dinner preferences, request acknowledgement and rule configuration previews.
- Responsive navigation, sticky employee names, accessible native dialogs and reduced-motion styles.

**Backend is not connected.** State lives under `shiftpilot-ui-demo-v1` in browser localStorage. Synthetic data and decision limits are labelled in the interface. No retired chat/payroll APIs are called. No real notifications, authentication, optimization, constraint certification, parser or transactional publication is provided.

Hours/base cost exclude breaks and overtime. Dinner coverage counts kitchen shifts spanning 18:00-22:00 against preferred targets; it is not a complete schedule metric.

## Verify

```powershell
npm run typecheck
npm run build
npm run test:e2e
```

Tests use installed Chrome without downloading browsers. Desktop/mobile checks cover navigation, locks/generation, publishing/reload/history, repair, team/request/demand interaction, dialog keyboard handling, overflow and automated WCAG A/AA checks on the roster. Automated accessibility checks do not replace assistive-technology testing. Screenshots go to `.impeccable/review/` (gitignored).

## Backend handoff and remaining work

See [BACKEND_HANDOFF.md](docs/BACKEND_HANDOFF.md). Local TypeScript shapes are presentation models, not frozen server contracts. Detailed availability/skills editing, employee self-service, CSV import wizard, command interpretation, rule compilation and live API integration remain follow-up slices.

Design references: [Taste Skill minimalist UI](https://github.com/Leonxlnx/taste-skill/blob/main/skills/minimalist-skill/SKILL.md), adapted for a dense operational roster; [Superdesign draft](https://p.superdesign.dev/draft/60a3db55-605b-483b-b5c6-a5ebb9c9d902). No external skill was installed globally.
