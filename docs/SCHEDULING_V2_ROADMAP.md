# ShiftPilot scheduling v2: evaluation and delivery roadmap

Reviewed on 18 October 2026 against the [v2 spec](SCHEDULING_V2_SPEC.md) (formerly `Newupdate.doc`), the existing planning documents, and selected implementation files. Resume positioning is excluded. This is a proposed implementation baseline, not evidence of working scheduling features. Existing DEV_PLAN task IDs describe the previous product and should not be used to implement this pivot.

Ownership revised to match the user's instruction: **Codex owns the entire UI; Claude owns the database, solver and backend.** This supersedes the ownership assignments in `DEV_PLAN.md` and `PARALLEL_WORK.md` for scheduling v2. The approximate 50/50 effort target does not permit splitting UI ownership.

Executable tasks, states, the handoff format and starting prompts are in [SCHEDULING_V2_TASKS.md](SCHEDULING_V2_TASKS.md). Deviations from the spec are recorded at the top of the spec itself.

## Product assessment

Proceed with the scheduling direction. Generation and repair form a coherent product loop, with deterministic optimization doing the decision work and optional natural language improving input. The first useful release is a manager opening a weekly roster, generating a draft, publishing it, reporting an absence, reviewing a repair and publishing the replacement.

The document is a strong vision but not yet an executable specification. Several examples contain illustrative numbers with no supporting model. The complete definition of done also includes substantial additional work: multi-outlet coordination, drag/resize, immutable history, restore, alternatives, infeasibility diagnostics, natural-language rules, employee workflows and imports. These must be explicitly owned rather than treated as incidental polish.

## Existing code: reuse and replacement

| Area | Evidence from source | Treatment |
|---|---|---|
| Identity and scope | `core/auth.py` has caller/role/outlet helpers; `db/session.py` sets tenant transaction context | Reuse concepts; test all scheduling resources. Existing owner checks assume tenant filtering and cannot replace it. |
| Database | Organizations, outlets, employees and shifts exist | Migrate deliberately. Current employee has one role; shifts use day/local times and a mutable row version. This is not schedule versioning. |
| Approvals | `mcp_server/actions.py` executes deductions; terminal replay happens before authorization | Reuse the pattern, not the implementation as a scheduling service. Add authorization before replay, transactional audit and stale-proposal checks. |
| API | Chat routes, demo identity, action decisions and reset exist | Add scheduling services/routes. Current reset calls the global seed loader; it cannot serve isolated public sessions. |
| Frontend | `web/README.md` describes a future chat app | Build the scheduling UI. There is no implemented roster UI to preserve. |
| Evals | Existing chatbot evaluation framework and cases | Reuse reporting ideas selectively; build scheduling scenarios and an independent validator. Old task-success scores do not measure roster quality. |
| Schema management | `db/init.py` uses `create_all`; dependencies do not list OR-Tools or Alembic | Add migrations, solver and reproducible dependency locking. Verify runtime compatibility during setup. |

Archive the previous scope in documentation; preserve old implementation until migration and replacement are verified. Do not continue payroll, policy retrieval, WhatsApp, voice, checklist or generic agent milestones for v2. Do not destructively remove existing data as part of the pivot.

## Decisions required in the implementation baseline

The following are recommended defaults, to be recorded before consumers implement the contracts.

1. **Coverage:** distinguish non-negotiable minimum staffing from preferred staffing. Minimums are hard; preferred shortfall is penalized. If a minimum is impossible, return infeasible and offer a separate, explicitly approved operating-policy change. A partial roster must visibly report its shortages. Define coverage as `sum(min(assigned, target) * interval_minutes) / sum(target * interval_minutes)` over role/outlet intervals; report minimum deficits separately and return N/A for zero demand. Overstaffing cannot inflate coverage.
2. **Hours and overtime:** separate regular-hours threshold, overtime permission and absolute weekly cap. Overtime permission never removes the absolute cap. Define daily/weekly premium interaction once, avoiding double counting. Use integer minutes and scaled integer cost coefficients in the solver; persist/display rounded money under a documented rounding rule. This is estimated roster cost, not payroll.
3. **Shift search space:** begin with configured shift templates and a 30-minute grid, including length and break rules. Manual edits use the same grid. Arbitrary continuous start/end optimization is deferred. Breaks reduce productive coverage when applicable. One employee supplies one role/skill capacity at a time.
4. **Time and boundaries:** use timezone-aware instants and outlet-local display. Include adjacent-week assignments when checking rest, overlap, travel and weekly limits. Distinguish same-workday split-shift travel from between-workday rest. The document's 17:00-to-17:35 transfer example otherwise conflicts with its 10-hour rest example. These are configurable business policies, not a claim of legal compliance.
5. **Absence and locks:** a new confirmed absence can invalidate a locked assignment. Record the absence as an operational fact, leave the published version immutable, flag the conflict and require explicit authorization to unlock/change the affected assignment. Unrelated locks remain fixed. Never silently ignore absence or move a lock.
6. **Optimization order:** hard validity first. For repair, prioritize minimum-demand shortfall, then disruption, then cost/preferences; use bounded staged solves and record whether each priority was proven optimal. Strategy profiles may vary only within agreed coverage/disruption guardrails. An arbitrary weighted sum must not buy large disruption for a small saving.
7. **Solver truth:** persist OPTIMAL, FEASIBLE, INFEASIBLE, MODEL_INVALID and UNKNOWN separately. A deadline with a valid incumbent may yield a feasible proposal; a deadline without a solution does not prove infeasibility. Separate solver outcome from job state and approval state. Record objective/bound, configuration and input hash; a feasible output is not automatically near-optimal.
8. **Alternatives and explanation:** run bounded strategy profiles, deduplicate equivalent schedules and return up to three genuinely different options. Do not promise three when only one exists. Candidate eligibility facts are different from a proven explanation of global optimality. Label bounded counterfactual checks as such; never infer a rejection reason solely from non-selection.
9. **Infeasibility:** start with deterministic shortage checks and supported assumption-group diagnostics. Suggest a bounded list of authorized relaxations and re-solve them. Do not promise globally smallest relaxations or a minimal unsatisfiable core. Availability, missing skills and absolute safety caps are never automatically relaxed.
10. **Unsupported estimates:** omit precise wait-time changes and live travel ETAs. No queueing model or location feed is specified. Use a configured travel matrix explicitly labelled as an estimate. Demand bands and historical samples are inputs, not a forecasting product.
11. **Publication and restore:** generated output is a draft. Manual edits to published schedules also require a reviewed publication. Reject stale proposals when relevant schedules, availability, rules, rates or demand change. Publish version, assignments, audit and delivery events atomically. Restore creates a new validated version; it does not erase history or revive an absent employee's shift blindly.
12. **Multi-outlet scope:** support three outlets from the start, with organization-wide conflict checks. Initial generation can be outlet-specific. Owner-authorized cross-outlet repair is included with atomic updates across affected outlets; broad joint optimization across all outlets is a later enhancement, resolving the document's inconsistent MVP/future descriptions.
13. **Employee and import scope:** basic own-schedule, availability, leave, absence and swap-request flows belong to the full v2 scope. Requests are not direct schedule writes. Include employee CSV preview/validation/commit; external messaging and automatic shift offers remain deferred.
14. **Tenant isolation:** every new tenant-owned table carries `org_id` (directly or through a composite foreign key) and has an RLS policy keyed on `app.org_id`, tested with the non-superuser runtime role. Add `app.role` to the session context as the spec requires. Today `db/session.py` sets only `app.org_id` and `app.user_id`. RLS is defence in depth for organization isolation. Outlet-level and employee-level authorization stays explicit in services and is tested separately.
15. **Runtime version:** the spec, `pyproject.toml` and the mypy configuration target Python 3.12, but the local `.venv` is Python 3.14.0. B0.1 picks one version, recommended 3.12 unless OR-Tools and every locked dependency are verified on 3.14. It rebuilds the environment and locks dependencies. CI, containers and both worktrees use the same version.

## Architecture and implementation boundaries

Use one modular Python backend, one web application and PostgreSQL. Run CPU-bound solver work in bounded worker processes with durable run records and restart recovery; do not block the API event loop or rely on in-memory background tasks for durable work. Browser polling is sufficient initially. Add a separate broker only if measured deployment needs justify it.

Suggested flow:

`validated input snapshot -> candidate shifts -> CP-SAT -> independent validator -> metrics/diff -> proposal -> authorized revalidation -> transactional publication`

The shared validator must check manual edits, solver proposals and restore operations. Its test implementation should calculate validity independently of the constraint-construction code so both cannot pass by repeating the same error.

Contracts must include organization/outlet scope, schedule ID and week, immutable base-version IDs, input revision/hash, request idempotency key, run status, candidate metrics, structured explanation facts, typed diffs and consistent errors. Add APIs missing from the vision's list: edit preview, candidate approval/rejection, version comparison/restore, demand configuration, employee requests, import and demo-session lifecycle.

Published schedules need a current-version pointer and stable logical shift identity across snapshots. Historical assignments must not be counted again as live employee commitments. Cross-outlet publication locks relevant schedule pointers and affected employees in stable order, then checks the current organization-wide roster. Composite ownership constraints prevent cross-tenant foreign-key links.

## Delivery phases and acceptance gates

Effort is combined focused person-days for both sessions, including normal task testing. Phases overlap where contracts permit; they are not equal-duration calendar sprints.

| Phase | Combined effort | Codex delivery | Claude delivery | Acceptance gate |
|---|---:|---|---|---|
| P0: baseline and contracts | 3–4 days | UI workflows/design direction, frontend setup and consumer contract review | Backend baseline, migration inventory, schemas, API fixtures and security/publication contract | Same fixtures parse in both lanes; baseline failures documented; no secret exposure |
| P1: domain and visible roster | 6–8 days | Weekly roster, outlet/week selectors, employee/skill/availability/demand forms and employee schedule view | Migrations, scoped data APIs, initial versions and deterministic seed | Three outlets/~60 employees displayed from real API; second-tenant and outlet-denial tests |
| P2: valid generation | 7–9 days | Generate/status/review UI, metrics/conflict displays and API integration | Shift templates, constraints, independent validation, worker/run lifecycle, objectives and baseline measurement | Valid weekly draft; locks/rest/skills/availability/hours/breaks checked; honest infeasible/timeout outcomes |
| P3: publish and manual control | 6–8 days | Drag/drop/resize, keyboard controls, validation preview, approval/history/compare/restore UI | Atomic approvals, edit validation, version history/diffs/restore, concurrency and idempotency | Publish/reload/restore works; stale/concurrent attempts cannot corrupt roster; manual edits use same rules |
| P4: absence repair | 6–9 days | Mobile absence/request UI, candidate comparison, explanation display, repair approval and E2E tests | Repair constraints/disruption, bounded alternatives, factual explanations and cross-outlet transaction | End-to-end absence -> review -> approval; unrelated commitments preserved; alternatives honestly reported |
| P5: rules and onboarding | 6–9 days | Command box, clarification/rule preview, employee request screens and CSV mapping/validation/commit UI | NL parsers, rule compiler, request workflows, CSV validation/staging/transactions and authorization | Supported commands/rules produce validated previews; unknown rules refused; invalid imports change no business data |
| P6: hardening and public demo | 6–9 days | Browser regression suite, mobile/accessibility finish, scenario launcher, report UI and frontend deployment | Backend deployment, isolated demo sessions/reset, limits, recovery, CI and scheduling/NL/security evaluations | Fresh deployment passes flows; 50+ scheduling and 30+ NL cases; published benchmark and permission evidence |

Total: **40–56 focused person-days before a 20–30% integration/uncertainty reserve**, or approximately **48–73 person-days with reserve**. With two consistently available sessions, budget roughly **6–9 elapsed weeks**, allowing for serial dependencies and human review. These are planning estimates, not measured agent speed or guaranteed dates. Re-estimate after P0 and P2. A narrower manager-only generation/repair beta can ship earlier after its publication and security gates; it is not the full v2 definition of done.

Start evaluation scenarios in P0/P1, security tests in P1, publication foundations in P1, and basic optimization metrics in P2. The document's M1–M9 order should not delay these until late milestones.

## A practical 50/50 division

Balance estimated effort, not lines of code or folder count. The following provisional 100-point budget gives each session 50 points; update it using completed-task evidence after P2.

| Work package | Codex points | Claude points |
|---|---:|---:|
| Contracts, baseline review and setup | 4 | 4 |
| Weekly schedule UI, drag/resize, keyboard access and responsive behavior | 16 | 0 |
| Employee, availability, demand and CSV onboarding UI | 10 | 0 |
| Repair, approval, history, restore, commands and rules UI | 10 | 0 |
| Browser/API integration, E2E tests and frontend recovery states | 8 | 0 |
| Database, migrations, authorization, APIs and publication transactions | 0 | 16 |
| Solver, constraints, repair, independent validation and worker lifecycle | 0 | 16 |
| NL parsing, rule compilation, import and employee-request backend | 0 | 8 |
| Scheduling/NL evaluations, security and backend fault tests | 0 | 4 |
| Frontend/backend deployment, demo integration and documentation | 2 | 2 |
| **Total** | **50** | **50** |

Points describe relative effort, not elapsed days. Codex owns every user-facing screen and interaction, frontend API integration and browser verification. Claude owns the database/backend implementation and its tests. This provisional budget is not proof of equal duration. If the backend becomes the bottleneck, revise the schedule or scope; do not transfer UI work to Claude or silently claim the split remains equal. Cross-review does not change exclusive write ownership.

**Expected bottleneck and agreed cut order.** The backend lane carries the serial critical path (schema → validator → solver → publication → repair), so it is the likely bottleneck from P2 onward. While blocked, Codex should take fixture-driven work: accessibility, mobile states, browser tests and error and recovery states. Codex should not wait idle or invent response shapes. If the P2 re-estimate shows the full scope will not fit, defer in this order, and record each deferral as an open definition-of-done gap rather than marking it done:

1. CSV import (B5.4/X5.3). Keep manual employee forms.
2. Employee swap requests (part of B5.3/X5.2). Keep own-schedule, availability, leave and absence.
3. NL commands (B5.1/X5.1). Keep NL rule creation, because it is a flagship demo step.
4. Third strategy profile. Keep two genuinely different alternatives.
5. Cross-outlet repair (B4.5). Keep organization-wide conflict checks and outlet-local repair.

Never cut: the independent validator, atomic publication and versioning, tenant and outlet isolation, lock preservation, honest solver and timeout status, or stale-proposal rejection.

Proposed exclusive write ownership:

- Codex: all of `web/`, including components, styles, design tokens, application routes, browser state, API clients, mock handlers, frontend package/lock files, browser tests and frontend deployment configuration. Includes every manager/owner/employee screen, mobile states, loading/empty/error states, notifications, demo controls and report presentation.
- Claude: `db/`, `core/`, `api/`, `scheduling/`, `commands/`, `rules/`, `employees/`, `schedules/`, `approvals/`, `audit/`, `importer/`, `seed/`, backend workers, `evals/`, `tests/` (Python/backend tests), backend dependencies/locks (`pyproject.toml` and its lock file), `.env.example`, backend `infra/` and CI (`.github/`). Owns authoritative metrics, explanations, eligibility checks and authorization.
- Claude also owns the legacy v1 directories, with these statuses (B0.2 confirms them):
  - `agent/`: frozen. Its model client (`agent/llm.py`) may be extracted into a v2 module for `commands/` and `rules/`. The LangGraph graph is not extended.
  - `mcp_server/`: frozen. `actions.py` is a reference pattern only. v2 approvals live in `approvals/`.
  - `jobs/`: the v2 scheduling worker either lives here or replaces it. B0.2 decides.
  - `rag/` and `voice/`: frozen, with no v2 work.
  - Frozen code is not deleted until its replacement is verified.
- `.gitignore`: either session may append entries for its own area only.
- Claude is the active writer for `contracts/`, backend fixtures and OpenAPI exports; Codex reviews them as the consumer before dependent implementation. Codex owns generated frontend client artifacts under `web/`. Contract changes require a versioned update and consumer handoff.
- Documentation: Codex owns UI, design and product-interaction documentation. Claude owns backend runbooks. Shared planning documents have one active writer at a time, assigned by the user. These are this roadmap, the task board, the spec and its deviations list, the root README and `REQUIREMENTS.md`. Claude holds that role as of 18 October 2026, by the user's instruction. Hand it over with an explicit note on the task board. The other session sends change requests rather than editing. Frontend and backend deployment files must be separate; agree shared deployment/CI edits before changing them.

Codex may calculate visual previews locally, but authoritative cost, coverage, conflict validity and publication permission come from Claude's backend. Pending previews must not appear as server-accepted changes. Claude returns structured explanation facts; Codex renders the complete explanation experience.

### Contract and integration handoffs

1. Claude supplies schemas and success/error/stale/denied/infeasible/timeout fixtures for each endpoint family. Codex begins UI work against reviewed fixtures without waiting for the entire backend.
2. Codex requests missing fields and workflows; Claude updates the provider contract before either side changes response shapes.
3. Integrate small slices: roster read -> edit validation -> generate -> publish -> absence/repair -> history/restore -> rules/import/employee requests.
4. Claude runs provider/database/solver checks. Codex runs consumer/build and real-API browser checks. Both must pass before a slice closes; mocks alone are not integration evidence.

A committed baseline now exists (commit `392fc5a`, 18 October 2026). Create worktrees from the current `main`. Give each session its own checkout, database and ports. Integrate small slices through contract and focused integration checks. No two sessions seed/reset the same database.

Every handoff includes task ID, commit, changed contracts, commands/results, migration effects, consumer instructions and known limitations. A browser mock is not a completed backend feature; a passing solver unit test is not a completed publishing workflow.

## Evidence required before calling v2 complete

- At least 50 scheduling scenarios covering ordinary, infeasible, overnight, boundary-week, locked, cross-outlet, repair, concurrent approval and restore behavior. At least 30 NL cases cover identity/date ambiguity, supported rules and unsupported/malicious input. Include a second tenant even though the public demo presents one organization.
- Zero hard violations in accepted fixtures and independent validation of every candidate before publication. Test outcomes support observed correctness; they are not a universal proof of bug-free execution.
- Compare a documented feasible greedy baseline and optimizer on identical inputs. Compare cost at matched coverage or report cost/coverage tradeoffs; do not require cost to fall when coverage has increased. Use exhaustive tiny instances to check objective calculations and minimum-change behavior where practical.
- Record solver status, bound/gap where meaningful, worker configuration, hardware, input/model size, time budget and repeated-run latency. Target p95 under 3 seconds for the defined ~60-employee weekly benchmark; measure full API/UI and multiple-candidate latency separately. Three strategy solves do not automatically fit a single-solve budget.
- Record absence-to-proposal latency and the under-10-second/three-click interaction target separately. Do not advertise manager time saved or acceptance rates without human-use evidence.
- Public demo sessions use synthetic isolated state, bounded optimizer concurrency and scoped reset/TTL cleanup. Real employee imports require private authenticated use; demo credentials must not grant access to private data.
- Reproducible clean setup, migrations, durable worker recovery, live browser flows and a report tied to code/configuration hashes. Model access, hosting account/budget and real-user acceptance remain human inputs; deterministic development can proceed independently.

## First assignments

Concrete first tasks are B0.1–B0.3 (Claude) and X0.1–X0.3 (Codex) in [SCHEDULING_V2_TASKS.md](SCHEDULING_V2_TASKS.md). The summary below describes each lane's overall scope.

**Codex:** own the entire schedule-first UI. Define desktop/mobile manager and employee workflows, review Claude's API fixtures, establish the frontend design system and build the weekly roster with outlet/week selection, employee/demand forms and generation/review states against agreed fixtures. Own subsequent editing, repair, approval, history, rules, import and employee screens, API integration and browser tests. Do not implement a chat homepage or invent backend response formats.

**Claude:** own database and backend delivery. Reproduce the backend baseline, draft the migration/schema plan and API contracts with synthetic fixtures, then implement tenant/outlet isolation, employee/availability/demand/version APIs and seed data. Continue with independent validation, CP-SAT generation/repair, atomic publication/restore, NL parsing/rule compilation, import, backend evaluations and deployment. Supply metrics/diffs/explanation facts and explicit error states to Codex. Do not modify `web/` or continue old F/T/A milestones as if they describe scheduling v2.

## Technical references checked

- Google OR-Tools CP-SAT status and integer-model guidance: https://developers.google.com/optimization/cp/cp_solver
- Official solver response definitions, including sufficient assumptions and solution bounds: https://github.com/google/or-tools/blob/stable/ortools/sat/cp_model.proto
- Official assumptions example: https://github.com/google/or-tools/blob/stable/ortools/sat/samples/assumptions_sample_sat.py

Validate installed package APIs and lock supported versions during P0. This review did not run the application, tests or performance benchmarks.
