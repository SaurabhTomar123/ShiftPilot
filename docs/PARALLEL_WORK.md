# Claude + Codex parallel work board

> **Historical work board for the previous product.** Use [SCHEDULING_V2_ROADMAP.md](SCHEDULING_V2_ROADMAP.md) for v2: Codex owns the entire UI; Claude owns the database, solver and backend. Do not use the assignments below for v2.

Read [DEV_PLAN.md](DEV_PLAN.md) for scope and [IMPLEMENTATION_CONTRACTS.md](IMPLEMENTATION_CONTRACTS.md) before implementation. This assigns work; it does not start agents or claim tasks are implemented.

## 1. Simultaneous working rules

1. Establish a reviewed repository baseline first. Project files were untracked at review time; worktrees require a committed baseline. Keep .env, tokens, private reports and DB dumps out of Git.
2. Use separate checkouts/worktrees and branches, such as codex/runtime and claude/web-evals. Give each a disposable database, Redis namespace and ports. Separate source directories do not isolate database mutations.
3. Codex freezes F1 schemas/fixtures first. Claude can review code/contracts and draft cases immediately, then implement fixture-based consumers after F1. Neither needs to wait for the entire backend.
4. Respect file ownership. Request changes from the owner rather than editing shared files simultaneously. Transfer ownership explicitly for coordinated exceptions.
5. Integrate small task branches after provider/consumer tests pass. Update both sessions to the new contract baseline before dependent work. Avoid weeks of divergent backend/frontend changes.
6. Cross-review security and measurement boundaries. Inspect/test the other lane freely; do not overwrite its work.

Each session takes one ready task at a time. Additional spawned agents are not needed for this split.

## 2. File ownership

| Owner | Exclusive mutation area | Boundary |
|---|---|---|
| Codex | core/, db/, mcp_server/, agent/, api/, rag/, infra/, .github/, seed/, importer/, root Python dependencies/locks/config, .env.example | Owns auth, business rules, persistence, routes and deployment. Secrets stay untracked. |
| Claude | web/ including its package/lock files; evals/; planned channels/; voice/; jobs/; planned docs/launch/ | Uses agreed service contracts; requests backend/config/seed changes from Codex. |
| Codex | Existing backend tests; new scheduling/API/agent/transport/migration/recovery/import tests | Claude does not concurrently edit those test files. |
| Claude | tests/test_graders.py; planned eval/golden-set/judge/report tests, tests/channels/, tests/voice/, tests/jobs/ and web E2E | Shared fixtures/DB setup changes go through Codex. |
| Codex integrates; both review | contracts/, planning docs, REQUIREMENTS.md, README.md, design decisions/threat model, shared test config | One active writer. Claude sends a patch/request. Product changes remain explicit decisions. |

Claude implements channel/job modules against F1 turn/action/inbox/outbox/job/delivery protocols with fakes. Codex implements storage, routes and startup wiring. If those protocols are not ready, mark integration blocked rather than inventing a competing API.

## 3. Task board

Status: ready, blocked (named dependency/input), in_progress, review, done. Task acceptance is in the plan. All tasks are initially unimplemented.

| ID | Owner | Initial state / prerequisites | Handoff |
|---|---|---|---|
| F0 | Codex | ready; live run needs credentials | Environment/check results and grounded answer or named blocker. |
| F1 | Codex + Claude review | ready | Schemas/fixtures and auth/error/date/report/service protocols. |
| F2 | Codex | blocked: F1 | Migrations, isolated reset and durable storage adapters. |
| T1 | Codex | blocked: F1 | Pure scheduling rules; future roster/ground truth. |
| T2 | Codex | blocked: F2, T1 | 12 tools and atomic audited decisions. |
| A1 | Codex | blocked: F2 | Turn service/eval adapter; memory/disambiguation. |
| A2 | Codex | blocked: A1, T2 | Recoverable approval/resume service. |
| A3 | Codex | blocked: A2 | SSE, HTTP MCP and trace contract. |
| W1 | Claude | blocked: F1 | Fixture-driven UI and consumer tests. |
| W2 | Claude | blocked: W1, A3 | Live integration and E2E flows. |
| E1 | Claude | blocked: F1 | Correct runner/metrics/report API, fake-provider tests. |
| E2 | Claude | blocked: E1, T1, A1 | 200 isolated valid cases; measured smoke selection. |
| E3 | Claude | blocked: E2, A3, human labels | Calibrated judge and first valid three-run report. |
| E4 | Claude; Codex API/CI | blocked: E3; H2 for final live publication | Dashboard and enforced/published baseline. |
| R1 | Codex | blocked: F2, E1 metrics contract | Retrieval/citations and eval evidence. |
| H1 | Codex | blocked: A1; final proof after A3 | Cache/limits/fault behavior and reliable runtime. |
| H2 | Codex | blocked: W2, E4 fixtures; final proof after R1 | Hosted demo/report sync and quality evidence. |
| C0 spike | Claude | blocked: F1 | Pipecat/WebRTC feasibility and meaningful-audio timing. |
| C1 | Claude; Codex wiring | blocked: A2, A3, H1, Meta access | Signed durable WhatsApp flow. |
| C2 | Claude; Codex wiring | blocked: C0, A3, H1, voice access | Authenticated voice/confirmation and latency traces. |
| C3 | Claude; Codex storage | blocked: F2 job protocol, C1 delivery | Durable anomaly/brief/weekly-report jobs. |
| I1 | Codex | blocked: F2, private-data boundary design | Staged mapping/validation/idempotent import API. |
| I2 | Claude | blocked: F1 import fixtures; final proof I1 | Import wizard and ≤10 min recording. |
| L1 | Claude drafts; Codex verifies | blocked: M4, M5, I2 | Evidence-backed launch materials. |

H2 packaging/CI can start early; final acceptance waits for consumers and measurements. E4 needs report fixtures and CI wiring, not a finished deployed H2, so the publication handoff is not a circular dependency. I1 can start once the private-data boundary is designed; it need not wait for all site polish.

## 4. Work packages

| Package | Codex | Claude | Integration point |
|---|---|---|---|
| A | F0/F1 → F2 | Review F1, inspect eval flaws, draft assertions | Both parse shared fixtures. |
| B | T1/T2 | E1 repair + W1 scaffold | Schema/action/metric contracts agree. |
| C | A1/A2 | W1 screens + E2 stable-seed cases | Persistent turns/pending cards pass both sides' tests. |
| D | A3 + deployment skeleton | W2 + E3 labeling packet | E2E flows and evidence-backed report. |
| E | R1/H1/H2 + report API/CI | E4 dashboard + C0/C1/C3 | M3 evidence, then M4 targets. |
| F | I1 + channel integration | C2/I2/L1 drafts | M5 latency and M6 onboarding/launch. |

These are not equal-duration sprints. If waiting, choose another ready test/consumer/review task; do not alter the other lane's API to bypass a blocker. W1/E1 share one Claude session, so prioritize E1's contracts/measurement before filling out screens.

## 5. Handoff format

Copy into a task note or linked PR:

```text
Task: <ID/title>
Status: <review | done | blocked: reason>
Branch/commit: <identifier>
Owned files changed: <paths>
Contract/schema version: <version; changes or none>
Behavior delivered: <observable result>
Verification: <commands/outcomes; report/trace IDs>
Migration/reset effects: <details or none>
Consumer action needed: <specific dependency or none>
Remaining limitations/external input: <details or none>
```

Done requires task-appropriate evidence. Fakes do not satisfy live-model checks; a missing key cannot make a live gate green. Agent prose cannot replace human judge labels, a recording or a measured result.

## 6. Copyable starting prompts

**Codex session**

```text
Read docs/DEV_PLAN.md, docs/IMPLEMENTATION_CONTRACTS.md and
docs/PARALLEL_WORK.md. Implement F0/F1 first, then take the next ready
Codex-owned task. Inspect applicable AGENTS.md instructions. Preserve
unrelated work and do not mutate Claude-owned files. Freeze schemas and
synthetic fixtures in contracts/v1 before changing public interfaces;
request Claude review. Use a disposable DB. Verify actual SDK/provider
support; never print secrets or claim live checks without running them.
Deliver focused code/tests and a handoff with commits, checks and blockers.
Start with this package; do not spawn additional agents.
```

**Claude session**

```text
Read docs/DEV_PLAN.md, docs/IMPLEMENTATION_CONTRACTS.md and
docs/PARALLEL_WORK.md. Inspect applicable AGENTS.md instructions. Your
first implementation tasks are E1/W1 after Codex freezes F1 fixtures.
Before that, review the contract and draft case/assertion examples.
Own web/ and evals/ initially. Do not edit backend, seed, migrations,
root dependencies, CI or shared config; send specific requests to Codex.
Use agreed fixtures/fake providers and a separate disposable database.
Repair per-turn grading, evidence, cost and numeric gates before adding
cases. Build web against the POST SSE and action contracts. Deliver
focused tests and a handoff. Do not fabricate human labels/live results
or start channels before their dependencies.
```

For later sessions, specify one ready task ID, the current integration commit and external blockers. Keep handoffs verifiable against code.
