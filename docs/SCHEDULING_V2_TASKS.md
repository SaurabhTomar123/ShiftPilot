# ShiftPilot scheduling v2: task board

Executable work for the [v2 roadmap](SCHEDULING_V2_ROADMAP.md). Product scope is in the [v2 spec](SCHEDULING_V2_SPEC.md) as amended by the roadmap's decisions. This board assigns work; it does not claim any task is implemented. v1 task IDs (F0, T1, W1, E1, …) in `DEV_PLAN.md`/`PARALLEL_WORK.md` are retired and must not be started.

**ID prefixes:** `B` = Claude (database, solver, backend). `X` = Codex (all UI under `web/`). `I` = joint integration gate; both sessions must pass their side. The number is the roadmap phase (P0–P6).

**States:** `ready`, `blocked: <dependency>`, `in_progress`, `review`, `done`. Update the state in this file when it changes. Only the current planning writer edits this file (Claude as of 18 October 2026). The other session reports state changes in its handoff, and the writer records them.

## Working rules

1. Branch from current `main` (baseline `392fc5a`). Each session uses its own worktree and branch, e.g. `claude/backend` and `codex/ui`, plus its own database, ports and Redis namespace if Redis is used. No two sessions seed or reset the same database.
2. Write only inside your own areas (roadmap, "Proposed exclusive write ownership"). To change the other lane's files, send a request; never edit them directly.
3. Contracts come first. Codex builds against reviewed `contracts/v2/` fixtures. Claude changes a response shape only through a versioned contract update and a consumer handoff.
4. Integrate in small slices through the `I` gates. A browser mock is not a finished backend feature. A passing solver unit test is not a finished publishing workflow.
5. Take one ready task at a time. While blocked, take another ready task in your lane, such as tests, fixtures, accessibility or review. Do not work around a blocker by changing the other lane's interface.
6. Never print secrets. Missing credentials or model access is a named blocker, never a silent pass.

## P0: baseline and contracts

| ID | Owner | State | Depends | Deliverable / acceptance |
|---|---|---|---|---|
| B0.1 | Claude | done | none | **Reproducible backend baseline.** Done: Python 3.14 chosen, `requirements.lock` added and all checks pass. See [runbook](runbooks/backend-baseline.md). Decide the Python version (roadmap decision 15). Rebuild the environment. Add and lock `ortools` and `alembic`, verifying the installed CP-SAT API. Run the existing lint, type checks and tests, and record the commands, counts and failures in `docs/runbooks/backend-baseline.md`. Update the `pyproject.toml` description to v2. |
| B0.2 | Claude | done | none | **Migration inventory and legacy plan.** Done: [v2-schema-plan](runbooks/v2-schema-plan.md). The worker lives in `scheduling/worker.py`, and demo sessions are per-session orgs. Map current tables (single `job_role`, `Shift.day/start_time/end_time`, mutable `version`) to the v2 schema: logical shift identity, immutable schedule versions, current-version pointer and composite tenant foreign keys. Plan the move from `create_all` to Alembic without stamping an unknown schema. Confirm the frozen, reuse or replace status of `agent/`, `mcp_server/`, `jobs/`, `rag/` and `voice/`, and decide where the worker lives. Output: `docs/runbooks/v2-schema-plan.md`. |
| B0.3 | Claude (Codex reviews) | ready | B0.2 draft for schema-shaped fields | **contracts/v2 for P1–P2.** Machine-readable schemas (OpenAPI or JSON Schema) and synthetic fixtures for: outlets, employees, skills, availability, demand, the schedule week read, and generate with run status and candidate metrics. Common conventions: IDs, timezone-aware instants with outlet-local display, integer minutes, money and rounding, the error envelope, idempotency keys, base version and input hash. Every endpoint family has success, denied, stale, infeasible and timeout fixtures where applicable. **Accept:** fixtures validate against the schemas in a backend test, and Codex records approval (X0.3). |
| X0.1 | Codex | ready | none | **Frontend setup.** Next.js, TypeScript (strict), Tailwind, shadcn/ui and dnd-kit at locked, verified versions. Lint, type check, unit test and Playwright scaffold. A mock layer that serves `contracts/v2` fixtures. **Accept:** clean install, build and test from the README in `web/`. |
| X0.2 | Codex | ready | none | **Workflows and design direction.** Manager desktop and mobile, owner and employee flows covering roster, generate and review, edit, publish, absence and repair, history and restore, rules, and import. Design tokens and the roster grid layout. Loading, empty, error, stale and denied states. **Accept:** written flows plus wireframes under `web/docs/`, reviewed by the user. |
| X0.3 | Codex | blocked: B0.3 | B0.3 | **Contract review.** Review contracts/v2 as the consumer. File requests for missing fields or workflows. Record approval of the contract version. |

**P0 gate:** both lanes parse the same fixtures, baseline failures are documented, and no secret is exposed.

## P1: domain and visible roster

| ID | Owner | State | Depends | Deliverable / acceptance |
|---|---|---|---|---|
| B1.1 | Claude | blocked: B0.1, B0.2 | B0.1, B0.2 | **Alembic migrations and v2 schema.** Organizations, outlets, skills, employee_skills, availability, preferences, staffing_requirements, schedules with a current-version pointer, schedule_versions, logical shifts and versioned assignments, optimization_runs and candidates, absences, rules, and append-only audit. RLS on every tenant table, `app.role` in the session context (decision 14), and composite ownership foreign keys. **Accept:** fresh upgrade works. Upgrading a populated v1 database loses no data. RLS is tested with the runtime role. |
| B1.2 | Claude | blocked: B1.1, B0.3 | B1.1, B0.3 | **Scoped data APIs** for P1 contract families. Outlet authorization in services. **Accept:** provider tests against contract fixtures. Second-tenant denial tests. A manager is denied other outlets. |
| B1.3 | Claude | blocked: B1.1 | B1.1 | **Deterministic seed and demo reset.** One org, three outlets, ~60 employees, five skills, demand bands, four weeks of demand history, one upcoming week, preferences, leave and deliberate conflicts (spec §49). Plus a second tenant for tests. Reset is tenant-scoped and never global; this replaces the current `/sandbox/reset` → `seed.load` path. **Accept:** identical output across runs, and reset leaves the second tenant untouched. |
| B1.4 | Claude | blocked: B0.3 | B0.3 | **Scenario format and first scenarios.** `evals/scheduling/` scenario schema plus 10 initial scenarios: normal, overnight, boundary week, locked, infeasible. Starting evaluation early is required by the roadmap. |
| X1.1 | Codex | blocked: X0.1, X0.3 | X0.1, X0.3 | **Weekly roster** with outlet and week selectors, metrics strip and coverage indicators, running against fixtures. |
| X1.2 | Codex | blocked: X0.1, X0.3 | X0.1, X0.3 | **Employee, skill, availability and demand forms**, including validation and server-error display. |
| X1.3 | Codex | blocked: X1.1 | X1.1 | **Employee own-schedule view** for mobile. |
| I1 | Both | blocked: B1.2, B1.3, X1.1 | B1.2, B1.3, X1.1 | **Roster read slice on the real API.** Three outlets and ~60 employees are shown from the backend. Denied outlet and second-tenant cases are visible as errors in the UI. |

## P2: valid generation

| ID | Owner | State | Depends | Deliverable / acceptance |
|---|---|---|---|---|
| B2.1 | Claude | blocked: B1.1 | B1.1 | **Independent validator.** Availability, skills and roles, overlap, rest and split-shift travel, weekly regular and absolute caps, breaks, locks, and adjacent-week context. Written separately from the CP-SAT constraint builder. **Accept:** boundary tests (9h59m/10h, overnight, week edge) and validation of every B1.4 scenario. |
| B2.2 | Claude | blocked: B2.1 | B2.1 | **Generation solver.** Shift templates on a 30-minute grid, CP-SAT hard constraints, hard minimum versus penalized preferred coverage, integer cost, strategy profiles within guardrails. Every output is validated by B2.1 before it is returned. |
| B2.3 | Claude | blocked: B1.1, B0.3 | B1.1, B0.3 | **Run lifecycle and worker.** Durable run records, bounded worker processes, restart recovery and idempotent requests. Job state, solver status and approval state are kept separate (decision 7). Inputs are snapshotted with a hash. |
| B2.4 | Claude | blocked: B2.2 | B2.2 | **Metrics, baseline and benchmark.** Coverage formula (decision 1), cost, overtime and preference match, plus a feasible greedy baseline. Benchmark on the ~60-employee week, recording the hardware, solver configuration and p95. **Accept:** optimizer versus baseline on identical inputs, compared at matched coverage or as a tradeoff. |
| X2.1 | Codex | blocked: X1.1, B0.3 | X1.1, B0.3 run fixtures | **Generate, status and review UI**, including metrics, conflicts and honest infeasible, timeout and unknown states. |
| I2 | Both | blocked: B2.2, B2.3, X2.1 | B2.2, B2.3, X2.1 | **Generate slice.** A real draft is generated and displayed, and an infeasible scenario is shown honestly. **Then re-estimate the remaining phases** and apply the roadmap cut order if needed. |

## P3: publish and manual control

| ID | Owner | State | Depends | Deliverable / acceptance |
|---|---|---|---|---|
| B3.1 | Claude | blocked: B2.1 | B2.1 | **Edit-preview API.** Manual move, resize, assign and role-change edits are checked by the shared validator, with structured reasons such as an earliest feasible start. |
| B3.2 | Claude | blocked: B1.1, B2.1 | B1.1, B2.1 | **Atomic publication.** Version, assignments, audit and delivery events are written in one transaction, with locks taken in stable order. Stale proposals are rejected and requests are idempotent. **Accept:** concurrent and duplicate publish tests cannot corrupt the roster. |
| B3.3 | Claude | blocked: B3.2 | B3.2 | **History, diff, compare and restore.** Restore creates a new validated version and never revives an absent employee's shift blindly. |
| X3.1 | Codex | blocked: X2.1, B3.1 contract | X2.1, B3.1 contract | **Drag, drop, resize and keyboard editing** with validation preview. Pending previews are never shown as server-accepted. |
| X3.2 | Codex | blocked: X2.1, B3.2/B3.3 contracts | X2.1, B3.2/B3.3 contracts | **Publish and approval, history, compare, restore and undo UI.** |
| I3 | Both | blocked: B3.*, X3.* | B3.*, X3.* | **Publish, reload and restore on the real API.** Stale and concurrent attempts are shown correctly, and manual edits follow the same rules as the solver. |

## P4: absence repair

| ID | Owner | State | Depends | Deliverable / acceptance |
|---|---|---|---|---|
| B4.1 | Claude | blocked: B3.2 | B3.2 | **Absence model and lock conflicts** (decision 5). |
| B4.2 | Claude | blocked: B2.2, B4.1 | B2.2, B4.1 | **Repair solver.** Staged priorities: minimum shortfall, then disruption, then cost and preferences. Bounded alternatives with deduplication, up to three (decision 8). |
| B4.3 | Claude | blocked: B4.2 | B4.2 | **Explanation facts.** Candidate eligibility facts and labelled bounded counterfactuals. A rejection is never inferred from non-selection alone. |
| B4.4 | Claude | blocked: B2.2 | B2.2 | **Infeasibility diagnostics.** Deterministic shortage checks plus authorized relaxations that are re-solved (decision 9). |
| B4.5 | Claude | blocked: B4.2, B3.2 | B4.2, B3.2 | **Cross-outlet repair transaction** (decision 12). Fifth in the cut order. |
| X4.1 | Codex | blocked: X3.2, B4.2/B4.3 contracts | X3.2, B4.2/B4.3 contracts | **Mobile absence flow**, candidate comparison, the "Why?" explanation and repair approval. |
| X4.2 | Codex | blocked: X2.1, B4.4 contract | X2.1, B4.4 contract | **Infeasibility and relaxation options UI.** |
| I4 | Both | blocked: B4.1–B4.4, X4.* | B4.1–B4.4, X4.* | **End-to-end absence → review → approval.** Unrelated commitments are preserved. Absence-to-proposal latency and the click count are measured. |

## P5: rules, requests and onboarding

| ID | Owner | State | Depends | Deliverable / acceptance |
|---|---|---|---|---|
| B5.1 | Claude | blocked: B3.1 | B3.1 | **NL command parser** using structured output and validation, with ambiguity questions. Its output is a preview and never a direct write. Third in the cut order. |
| B5.2 | Claude | blocked: B2.2 | B2.2 | **NL rule parser and compiler** with an affected-employees preview. Unsupported rules are refused. |
| B5.3 | Claude | blocked: B4.1 | B4.1 | **Employee request backend** for availability, leave, absence and swap requests. Swap requests are second in the cut order. |
| B5.4 | Claude | blocked: B1.2 | B1.2 | **CSV import**: preview, mapping, validation, staging and one-transaction commit. Invalid imports write no business rows. First in the cut order. |
| X5.1 | Codex | blocked: X2.1, B5.1/B5.2 contracts | X2.1, B5.1/B5.2 contracts | **Command box, clarification and rule preview.** |
| X5.2 | Codex | blocked: X1.3, B5.3 contract | X1.3, B5.3 contract | **Employee request screens.** |
| X5.3 | Codex | blocked: X1.2, B5.4 contract | X1.2, B5.4 contract | **CSV mapping, validation and commit wizard.** |
| I5 | Both | blocked: B5.*, X5.* | B5.*, X5.* | **Rules, requests and import slice.** Supported inputs produce validated previews and unknown rules are refused. |

## P6: hardening and public demo

| ID | Owner | State | Depends | Deliverable / acceptance |
|---|---|---|---|---|
| B6.1 | Claude | blocked: I4 | I4; NL cases after B5.1/B5.2 | **Evaluations.** 50+ scheduling scenarios, 30+ NL cases and security cases. A report tied to code and configuration hashes. |
| B6.2 | Claude | blocked: B1.3, B2.3 | B1.3, B2.3 | **Demo sessions.** Isolated synthetic state, scoped reset with TTL cleanup, bounded optimizer concurrency and rate limits. |
| B6.3 | Claude | blocked: I3 | I3 | **Backend deployment and CI.** One-shot migrations, worker recovery and fault tests. |
| X6.1 | Codex | blocked: I4 | I4 | **Browser regression suite** plus mobile and accessibility finish. |
| X6.2 | Codex | blocked: B6.2 contract | B6.2 contract | **Demo scenario bar and report UI.** |
| X6.3 | Codex | blocked: X6.1 | X6.1 | **Frontend deployment.** |
| I6 | Both | blocked: B6.*, X6.* | B6.*, X6.* | **Release gate.** A fresh deployment passes every flow. The README is rewritten for v2 by the planning writer, and the roadmap's evidence list is checked item by item. |

## Handoff format

```text
Task: <ID/title>
Status: <review | done | blocked: reason>
Branch/commit: <identifier>
Owned files changed: <paths>
Contract version: <version; changes or none>
Behavior delivered: <observable result>
Verification: <commands and outcomes; report IDs>
Migration/reset effects: <details or none>
Consumer action needed: <specific request or none>
Remaining limitations/external input: <details or none>
```

## Starting prompts

**Claude session (database, solver, backend)**

```text
Read docs/SCHEDULING_V2_ROADMAP.md, docs/SCHEDULING_V2_TASKS.md and the
deviations list at the top of docs/SCHEDULING_V2_SPEC.md. DEV_PLAN.md,
PARALLEL_WORK.md, IMPLEMENTATION_CONTRACTS.md and REQUIREMENTS.md are
historical v1 documents; do not implement from them. You own the database,
solver and backend areas listed in the roadmap; never modify web/. Start
with B0.1 and B0.2, then B0.3 (contracts/v2 with fixtures) for Codex to
review. Work in your own worktree, branch and database. Verify installed
OR-Tools/Alembic APIs rather than assuming them. Deliver focused code and
tests plus a handoff in the board's format. Do not continue v1 milestones.
```

**Codex session (all UI)**

```text
Read docs/SCHEDULING_V2_ROADMAP.md, docs/SCHEDULING_V2_TASKS.md and the
deviations list at the top of docs/SCHEDULING_V2_SPEC.md. DEV_PLAN.md,
PARALLEL_WORK.md, IMPLEMENTATION_CONTRACTS.md and REQUIREMENTS.md are
historical v1 documents; do not implement from them. You own everything
under web/ and nothing outside it; send backend requests to Claude. Start
with X0.1 and X0.2, then review contracts/v2 (X0.3) when B0.3 lands. Build
against reviewed fixtures only; never invent response shapes, and never
show a pending preview as server-accepted. The homepage is the schedule,
not a chat box. Work in your own worktree, branch and ports. Deliver
focused code and tests plus a handoff in the board's format.
```
