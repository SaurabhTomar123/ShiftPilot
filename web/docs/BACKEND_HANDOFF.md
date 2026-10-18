# Scheduling UI: first backend handoff

18 October 2026. Codex implemented a browser-local UI demo in `web/`. Claude owns the backend. This requests provider contracts; it does not freeze endpoint names or assign shared `contracts/` edits to Codex.

## Delivered consumer flows

Roster read/filter -> shift edit/lock -> sample generation -> publication -> history/restore. Separate absence -> replacement selection -> draft update. Team, demand preferences, request acknowledgement and rule configuration previews are reachable from the sidebar.

The only persistence is browser localStorage. Local publish/acknowledge/repair actions are not backend capabilities. `src/lib/demo.ts` and `types.ts` contain synthetic view models, not the final database model. No backend source was changed.

## Provider contracts requested, in integration order

Supply versioned OpenAPI/schema definitions and success/error/denied/stale/infeasible/timeout fixtures for each slice:

1. **Bootstrap/roster:** identity/capabilities, permitted outlets, employee display data, roles/skills, timezone, week and immutable base version. Distinguish absent shifts, unassigned requirements and days off.
2. **Edit preview/draft:** stable logical shift ID, timezone-aware start/end, role/skills, assignment/outlet, lock state, structured validation issues, authoritative cost/coverage, typed diff and draft revision. Support keyboard reassignment as well as drag gestures.
3. **Generate/run/candidates:** idempotent key, immutable input revision/hash, strategy, durable run ID, separately typed job/solver/proposal states, bounded polling, objective/bound and candidate details. No auto-publication.
4. **Publication/history/restore:** candidate/draft, expected base versions, approved diff, scoped authority, stale-conflict response, audit actor/time. Restore previews a newly validated draft; immutable versions cannot be overwritten.
5. **Absence/repair:** operational absence status, affected assignments, locks requiring resolution, factual eligibility/rejection reasons and validated multi-outlet diff. Return up to three distinct strategies, never fabricated alternatives.
6. **Demand/requests/rules:** mandatory minima versus preferred staffing; effective dates; leave/availability/swap request status distinct from schedule application; typed supported rules, source text, validation and clarification.
7. **Import/commands/demo lifecycle:** staged CSV mappings/validation/commit, scoped idempotency, confirmed structured commands/rules, isolated demo session/reset/expiry.

## Consumer expectations

- Scope reads by outlet AND week; scope employees/requests explicitly. UI filtering is not authorization.
- Return authoritative metrics and structured explanation facts. Demo calculations will be replaced.
- Return stable error codes, recovery text and trace/run IDs, without internal dumps.
- Money needs exact representation and currency; timestamps need explicit timezone semantics. Integer-rupee demo rates must not become a server contract by accident.
- Agree session transport before live integration. Never expose admin credentials in frontend environment variables.
- Claude owns provider schemas, fixtures, implementation and tests. Codex owns the typed frontend adapter and all UI. Coordinate schema changes before consumers change.

## Limitations

The editor is a local preview, not a scheduling validator. Native drag is desktop-only; the dialog supports keyboard time/lock editing, while full keyboard reassignment remains follow-up. Demo alternatives check role/day occupancy only. Real CSV import, NL parsing, detailed skills/availability and employee self-service are not implemented. This UI establishes no solver, optimization or authorization evidence.

Each handoff includes commit, contract version, migrations, commands/results, fixtures and limitations. Both lanes must pass real-API integration before closing a feature.
