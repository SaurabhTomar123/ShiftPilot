# ShiftPilot development plan

> **Scheduling v2 supersedes this plan.** Use [SCHEDULING_V2_ROADMAP.md](SCHEDULING_V2_ROADMAP.md): Codex owns the entire UI; Claude owns the database, solver and backend. The assignments below are historical context for the previous product.

Reviewed against the repository on **16 October 2026**. This is an implementation plan, not a claim that unfinished features work.

Read in order:

1. **This file:** what to build, dependencies, acceptance criteria.
2. [Implementation contracts](IMPLEMENTATION_CONTRACTS.md): technical rules both agents must implement identically.
3. [Parallel work board](PARALLEL_WORK.md): Claude/Codex ownership, handoffs, and starting prompts.

[REQUIREMENTS.md](../REQUIREMENTS.md) remains the product specification. Conflicts are recorded explicitly; do not quietly change requirements to make a test pass. Task IDs below replace the old subtasks; M1–M6 retain the spec's milestone meanings.

## 1. Issues corrected

| Issue found in the plan or code | Correction |
|---|---|
| Headline says 38 days; milestone headings total 39. M2 subtasks total 11 rather than 9. Testing/integration are underbudgeted. | Effort ranges and dependency gates; two agents do not halve elapsed time. |
| Environment, passing tests, installed versions and model availability are asserted without current evidence. | Separate source inspection from execution evidence; verify in F0 without printing secrets. |
| Organization RLS is treated as outlet/user authorization. | Explicit access checks for conversations, actions, audit, imports and checkpoint threads. |
| Staff checklist self-approval contradicts spec §1 and `can_approve`. | Manager/owner checklist changes initially; staff checklist support requires an explicit spec decision. Staff never approve. |
| Owner approval for a manager's own swap is invented. | Keep manager self-confirmation within authority, as the spec permits. |
| Future-only swaps have little useful data with the demo clock at the last seeded day. | Add a deterministic future roster and documented date semantics. |
| Checkpointed graph state would contain bridges, mutable usage and caller objects. Interrupt replay can duplicate proposals. | JSON-compatible state, runtime dependency injection and a separate interrupt node after durable proposal creation. |
| The synchronous LiteLLM wrapper is assumed to stream through LangGraph automatically. | Explicit streaming adapter and event sink; graph updates alone are not token streaming. |
| A replace event is treated as protection against already displayed/spoken invented numbers. | Progress streams immediately; answer chunks publish only after verification. Record the latency tradeoff. |
| Every error says nothing changed, even after a committed approval. | Durable action status is independent of model narration; reconcile uncertain outcomes before retry. |
| Shift versions alone cannot prevent concurrent conflicting assignments to different shifts. | Serialize by affected employee, revalidate schedules in the transaction, then update both shifts atomically. |
| `decide()` returns terminal results before checking approver authority; decisions lack transactional audit. | Authorize replay reads; commit mutation/status/decision audit/resume work together. |
| Evals grade only the last turn, count only its cost, and send call metadata rather than results to the judge. | Repair measurement before adding cases or publishing results. |
| Numeric accuracy is not reported/gated; missing baseline can silently disable comparisons. | Explicit denominators, compatibility metadata and missing-evidence behavior. |
| A fused retrieval score is treated as universal confidence. | Tune abstention on development queries separately for hybrid/FTS-only; report held-out quality. |
| Public demo auth/reports and global reset are unsafe for imported data. `seed.load` truncates all tables. | Separate synthetic public demo from private imports; tenant-scoped reset before deployment. |
| Reports on a Git branch do not update the running API. Nightly cost policy contradicts the workflow. | Tested report synchronization; default model nightly, four-model comparison weekly/manual. |
| Migrations and API/agent tests arrive too late. PDF ingestion, conversations UI, policy faithfulness, weekly ops report and resume/outreach lack owned work. | Start foundations/tests immediately and track all required outputs. |

## 2. Starting point: inspected, not re-certified

| Area | Source inspection establishes | Still needs proof |
|---|---|---|
| Tools | Eight read tools and deduction proposal registered; three proposals/executors absent. | Runtime schemas, tool unit coverage ≥90%, authorization paths. |
| Agent | Guard/router/tool loop/verifier/responder exist; HTTP bridge is a stub; client supplies history. | Real-model correctness, persistent memory, streaming, restart/resume. |
| API | Demo tokens, chat, final-only SSE, action decisions and global reset exist. | Resource authorization, safe errors, tests, rate limits. |
| DB | Models and organization RLS bootstrap exist; runtime uses a non-superuser connection. | Versioned migrations, new metadata, checkpoint isolation. |
| Evals | Starter JSONL set, runner, graders, judge and workflows exist. | Correct metrics, calibrated judge, compatible baseline, reproducible comparison. |
| Delivery | Compose contains Postgres/Redis; web has scaffold instructions. | Full containers, hosted app, channels, importer, launch evidence. |

Do not assume API keys are empty or tests pass. F0 records actual versions, test counts/outcomes and provider access without exposing credentials. This documentation review does not certify runtime behavior or change application code.

## 3. Delivery strategy

**First useful release:** M1 tools, then M2 deployed web demo with a small trustworthy smoke suite. M3 makes measurement credible, M4 meets quality/performance targets, M5 adds channels, M6 finishes onboarding/launch. Channels/import remain required for full completion but do not block the first usable web release.

**Ownership:** Codex owns backend/runtime/security/infrastructure. Claude owns web/eval content/reporting/channel modules. This is a file-boundary decision, not a claim that one model is inherently better. Both review integration contracts.

The task-card estimates total **52–78 focused person-days**, including tests and the early voice spike within tasks, before a **20–30% integration/rework reserve**. These are planning estimates, not measured delivery promises. With two active sessions and prompt human input, allow roughly **8–12 elapsed weeks**; access, approvals and latency research can extend this. Re-estimate after F2 and the voice spike.

| Wave | Codex | Claude | Gate |
|---|---|---|---|
| Foundation | F0/F1, then F2 | Review contracts; after F1, E1/W1 against fixtures | Shared schemas and working migration |
| Tools + skeleton | T1/T2 | E1/E2; W1 fixture-driven screens | M1 |
| Working demo | A1/A2/A3, deployment skeleton | W2 integration; E3 labeling packet | M2 |
| Measurement + quality | R1/H1/H2; report API/CI | E3/E4 dashboard; early voice spike | M3, then M4 |
| Channels + launch | Channel wiring, I1 import API | C1/C2/C3, I2 wizard, L1 | M5, then M6 |

Backend dependency chain: **F1 → F2 → A1/T2 → A2 → A3 → W2 → deployed demo**. Quality additionally depends on corrected evals, retrieval and real runs. Claude starts consumers after F1, without waiting for all backend work. The work board resolves shared files and integration order.

## 4. Task cards

Suggested new paths are planned files. Every task needs evidence in its handoff before becoming done.

### F0 — Reproduce the baseline

**Codex · 1–2 d · Depends: none · Paths: environment notes in docs; build/dependency configuration.**

- Inventory Python, Node, MCP, LangGraph, LiteLLM and Langfuse versions. Start with shared Python 3.12; verify compatibility and lock dependencies. Validate SDK APIs from installed code and current official docs when implementing.
- Run lint, configured strict typing, unit tests and DB integration tests against a disposable DB. Record commands/counts/failures and commit identity; fix failures in the owning task.
- Verify router/main/fallback IDs through minimal real requests. Reading `settings().main_model` proves parsing only. Configuration strings are not availability evidence.
- Human supplies credentials, repository/account access and a strong JWT secret. Never print secret values. Repository creation/push and provider setup remain explicit access tasks.
- **Accept:** environment/results note and one real pay answer matching tool evidence, or a named external blocker while deterministic work continues. Save a provisional report; do not bless incomplete metrics as a final baseline.

### F1 — Freeze shared contracts

**Codex; Claude reviews · 1 d · Depends: source review · Paths: companion contract document; planned contracts/v1/.**

- Produce machine-readable request/response/SSE/report schemas, service protocols and synthetic fixtures from the companion document. Specify errors, action states, owner checks, pagination, dates and money.
- Claude builds fixture-based consumers; Codex implements providers. Coordinate schema/fixture changes before dependent implementation changes.
- **Accept:** both lanes parse the same fixtures, including denied access, failed narration after commit, and missing eval evidence. Each surface has a provider and consumer test owner.

### F2 — Migrations and environment isolation

**Codex · 2–3 d · Depends: F1 · Paths: db/, core/config.py, seed/load.py, dependencies, migration tests.**

- Add Alembic: initial schema, extensions, indexes, constraints, grants and RLS. Separate migration/admin, app and checkpoint privileges. Inspect a populated existing DB before stamping; never stamp an unknown schema.
- Add required message/intent/prompt/model/evidence metadata, turn request deduplication, proposal/thread linkage, checklist versioning and durable inbox/outbox/job records. New tenant tables get isolation tests.
- Replace runtime global reset with demo-tenant-only reset, invalidating its histories/checkpoints/cache while preserving other tenants and audit retention. Keep whole-DB seeding explicit and disposable-development-only.
- **Accept:** fresh upgrade; populated-baseline upgrade without data loss; least-privilege runtime; append-only audit; reset cannot alter a second tenant. Ordinary startup never seeds/resets data.

### T1 — Pure scheduling rules and useful fixtures

**Codex · 2–3 d · Depends: F1 · Paths: planned core/scheduling.py, tests/test_scheduling.py, seed/generate.py.**

- Evaluate full datetimes in outlet timezone, including overnight shifts. Exclude original assignments during a swap; reject identical shifts, same-person no-ops, inactive employees, role mismatch and unsupported cross-outlet moves.
- Validate both incoming schedules: future scheduled shifts, overlap, ≥10 h rest before/after, and handbook §6.3's ≥24 h swap notice. Reassignment has no invented 24 h rule.
- Add future shifts beyond the frozen demo clock without fabricating attendance. Update affected ground truth and relative-date cases.
- **Accept:** 9 h 59 m/10 h and 23 h 59 m/24 h boundaries, adjacent/overnight days, no-op/role/outlet tests, deterministic fixture output. Document enforced handbook rules versus policy-only guidance.

### T2 — Complete proposals and atomic approvals

**Codex · 3–4 d · Depends: F2, T1 · Paths: core/auth.py, mcp_server/, bridge registration, tool/auth tests.**

- Implement swap/reassignment/checklist proposals and executors. Register all 12 tools in MCP and the in-process bridge with identical input validation/envelopes. A1 updates graph intent scopes.
- Staff propose only own swaps and never approve. Checklist changes initially require manager/owner. Recheck identity, authority, outlet, expiry, versions, period state and business rules when deciding; authorize terminal-result replays too.
- Serialize scheduling changes by affected employee in stable ID order, then lock/version-check shifts, query neighboring assignments, and update atomically. A stale second update rolls back the first.
- Make proposal retries concurrency-safe with stable request identity and DB uniqueness. Replay/double tap cannot duplicate work; a deliberately new identical request remains possible.
- Reject non-finite deduction amounts. Enforce handbook weekly deductions ≤50% of gross using deterministic payroll computation and employee/period serialization. ₹2,000 is manager-authorized; ₹2,000.01 needs owner. Recheck cap at execution.
- Commit mutation, terminal status, decision audit and resume-outbox record together. Executor savepoint rollback preserves failed status/audit without partial business writes.
- **Accept:** competing decisions, concurrent conflicting assignments, stale versions, terminal replay authorization, rejected/expired/failed actions, deduction limits/cap, audited outcomes. ≥90% unit coverage on tool modules; integration coverage reported separately. Claude Desktop screenshot is separate demo evidence.

### A1 — Persistent conversations and disambiguation

**Codex · 3–4 d · Depends: F2 · Paths: agent/, planned api/routes/ and api/services/, graph/API tests.**

- Public chat accepts `conversation_id` and `client_request_id`, never client history/tool messages. Load authorized server history and resolved entities. Define 20 turns as 20 user/assistant exchanges subject to token budget.
- Persist canonical answer/evidence/intent/usage/models/prompt version/trace/status per turn. Deduplicate requests and allow one active turn per conversation. Persona switching starts a separate conversation.
- Refactor executor into resumable model/tool steps. Router extracts dates with an injected clock. Ask one disambiguation question and stop before a dependent call; next turn resolves from memory. Ambiguous “kal” needs clarification.
- Persist JSON-compatible IDs/messages/evidence/counters, injecting caller/bridge/sessions/callbacks at runtime. Strengthen grounding beyond token membership: signed values bound to entity, period and measure, including dates/times/counts where stated.
- **Accept:** fake-model tests for tool loop, entities/corrections, date ambiguity, step limit, retries, concurrent turns, ordering, wrong entity/period/sign, and same-org unauthorized conversation IDs.

### A2 — Durable interrupt and recovery

**Codex · 2–3 d · Depends: A1, T2 · Paths: agent/, approval service/routes, checkpoint/recovery tests.**

- Add compatible Postgres checkpointer lifecycle. Authorize org/user conversation access before every graph operation; checkpoint tables do not automatically inherit domain RLS.
- Interrupt in a separate node after durable proposal/result storage. Initially allow one outstanding action per conversation; later action requests wait for its decision.
- A manager can approve a staff request without reading the staff conversation. Resume only the stored original thread, with original requester visibility and stored executor evidence. Never trust caller-supplied thread/resume payloads.
- Resume via durable outbox with unique action-result delivery identity. Duplicate delivery cannot add proposals, mutations or visible duplicate replies.
- **Accept:** restart before approval; crash after commit before resume; retry after narration failure; rejection/expiry; wrong-thread/user denial. Durable execution status remains readable if the model is unavailable.

### A3 — Honest SSE, HTTP MCP and traces

**Codex · 3–5 d · Depends: A2, F1 · Paths: agent/llm.py, agent/tools_bridge.py, API stream/trace integration, transport tests.**

- Implement async/cancellation-aware model streaming and explicit node/tool events. Do not assume synchronous LiteLLM emits LangGraph message chunks. Remove `asyncio.run` from async runtime paths.
- Stream progress immediately; buffer drafts through verification, then emit verified answer chunks and one final. This deliberately trades speculative text latency for grounding; `replace` is reconciliation, not a safeguard after leaking drafts.
- POST SSE uses authenticated fetch, event IDs, heartbeat, disconnect cancellation and persisted-state reconciliation. Show work exposes authorized result projections, never private/internal dumps.
- HTTP MCP needs bounded sessions, timeout/reconnect/token refresh/cleanup. Missing HTTP auth must never fall back to the stdio demo identity. Current CLI shape is `--http --port 8001`, not `--http :8001`; validate installed SDK behavior.
- Generate trace ID before failure; spans per node/tool/provider; actual retry costs; redaction before export; graceful trace-export failure. Verify installed Langfuse APIs instead of assuming decorator paths.
- **Accept:** bridge parity for representative reads/proposals/errors; missing/forged/expired token denial; no session identity leakage; forced verifier rewrite exposes no draft number; disconnect and trace-export fault tests.

### W1–W2 — Web, first mocked then integrated

**Claude · 5–7 d · Depends: W1 F1; W2 A3 and audit/report contracts · Paths: web/ only.**

- W1: strict TypeScript app with a supported locked frontend release, fixture-driven chat, six prompts per role, owner/three managers/two staff personas, outlet badge, Show work, approvals, audit and conversations screens.
- W2: real POST SSE, history, approve/reject/recovery status, verified chunks, reset, expiry countdown and role switching. Cancel/clear the previous persona's stream/state; server decides permissions/expiry.
- Include keyboard/mobile support, loading/empty/error states, pending-action read-only state, no duplicate finals and correct currency display. Request missing APIs from Codex rather than editing backend files.
- **Accept:** build/type/lint plus five Playwright flows: role + answer; propose + approve + net pay; colleague-pay refusal; disambiguation across turns; owner reset. Verify reload recovery and no old-persona data.

### E1–E2 — Fix measurement, then reach 200 cases

**Claude · 5–7 d · Depends: E1 F1; E2 E1, T1 fixtures, A1 adapter · Paths: evals/ and eval tests; seed changes via Codex.**

- E1: record checks/evidence on every turn, action decisions and final DB state; sum all-turn latency/tokens/cost. Record requested/actual models and fallbacks. Separate judge/embedding overhead. Empty selections cannot pass.
- Judge receives actual tool results. Add explicit argument and numeric correctness metrics/gates with eligible denominators; required omissions fail. Test boundary/missing-baseline/incompatible-report/provider-failure behavior.
- E2 category targets: lookup 50, pay 35, actions 30, policy 25, multi-turn 20, security 25, messy input 15 = 200. At least two smoke cases per category; final smoke count must be measured under 4 min, not assumed from 25 sequential cases.
- Use dataset fact references, fixed seed/clock, two-tenant security fixtures and an injection note reachable through a tool. Isolate case/run mutation state and worker DBs. “Pending ID exists” does not prove approved execution was correct.
- **Accept:** 200 unique valid cases with resolving refs/personas/categories; per-turn assertions and final-state checks; deterministic measurement tests using fakes; provider errors remain failures, never dropped to improve scores.

### E3–E4 — Judge, reports, dashboard and CI

**Claude; Codex API/CI wiring · 3–5 d · Depends: E2, A3; final publication H2 · Paths: evals/, web/; API/workflows via Codex.**

- Version judge prompts and implement calibration CLI. Human labels 40 balanced pass/fail answers with reasons; model-generated labels are not human calibration. Predefine score-to-pass threshold; report ≥85% agreement, Cohen's κ and holdout results.
- Judge family differs from answer-producing families, including fallback, for each candidate. Invalid judge output/outages are unavailable/failing evidence, not passing judgments.
- Immutable reports include schema/git/case/seed/prompt/clock/config hashes, requested/actual models, prices/FX, counts/errors and gate outcomes. Review baseline promotion; never overwrite baseline before gating a candidate.
- Public dashboard: trends, model table, failure taxonomy and case/turn/evidence drill-down from sanitized synthetic reports. Codex supplies scoped/paginated audit/report APIs, safe run-ID lookup and atomic report download/refresh to a read-only configured directory.
- Every PR runs deterministic checks. Paid smoke requires trusted context/secrets; fork PRs remain secret-free and explicitly unavailable for live eval. Nightly full ×3 on default model; weekly/manual comparison ≥4 models with fixed router/fallback policy. Privileged comment workflows never execute untrusted PR code.
- **Accept:** human calibration packet/results; real three-run report; dashboard refresh after publication; compatible baseline and numeric/security/regression gates; measured <4 min smoke; summary/artifact posted safely. Missing keys cannot produce green live-eval evidence.

### R1 — Hybrid policy retrieval and faithful citations

**Codex · 2–3 d · Depends: F2, E1 retrieval metrics · Paths: rag/, policy search, migrations/retrieval tests.**

- Heading-aware Markdown/PDF extraction, stable chunk IDs, versioned idempotent embeddings, dimension/model checks, tenant filters and HNSW migration; re-embed changed content.
- Cosine top 20 + FTS top 20 → RRF(k=60) → top 5. Missing embeddings/provider outage falls back to bounded FTS; no hits is valid.
- Tune abstention separately for hybrid/FTS-only on development queries. Fixed RRF scores are not probabilities. Evaluate held-out hit@5, citation validity and faithfulness.
- **Accept:** expected section retrieval, unrelated-query abstention, cited-hit checks, PDF sample, embedding-outage behavior and tenant isolation.

### H1–H2 — Reliability, abuse limits, deployment and quality

**Codex; Claude UI/eval consumers · 5–8 d · Depends: foundations early; final W2, E4, R1 · Paths: core/, agent/, api/, infra/, .github/, root config.**

- H1: 5 s tool deadline, 20 s provider-attempt timeout, at most two retries for retryable errors and bounded overall turn deadline. Cancelling an async wrapper around a blocking thread does not undo a write; implement safe cancellation/status recovery.
- Breaker: five retryable provider failures/60 s → open 2 min → half-open probe. Record fallback. Authorized read cache 60 s keyed by org/user/role/outlet/tool/args/data generation; invalidate on write/reset/import; never cache proposals.
- Shared Redis limits: 30 messages/min/user, cumulative 20k conversation tokens, eight loop iterations plus bounded tool calls per iteration. Count retries/resumes/concurrency. Specify fail-closed behavior when shared limits are unavailable.
- H2: non-root API/MCP/web containers, health/readiness, one-shot migration and explicit demo seed setup, service-DNS URLs, CORS config, strong-secret checks, report sync, persistent DB/checkpoints, shutdown cleanup and backup/restore.
- Public demo tokens/reset apply only to synthetic data; private imports use a separate private environment without demo-token minting. API/web runtime must not have unrestricted admin credentials; replace current admin identity/reset paths with least-privilege services.
- Measure full-suite task ≥92%, tool ≥95%, numeric/security 100% over three runs. Text p50 ≤3 s/p95 ≤6 s, mean conversation cost ≤₹0.50 and cold readiness <10 s (excluding first provisioning/migrations) remain explicit targets; demo onboarding <30 s is different.
- **Accept:** provider/Redis/DB fault tests, cache invalidation, bounded retries, ambiguous commits, clean-clone Compose, deployed E2E, real Langfuse traces and four-model results with fallback disclosure. Iterate largest failure bucket and log before/after. M4 stays open if targets fail unless spec changes explicitly.

### C1–C3 — WhatsApp, voice and jobs

**Claude modules; Codex routes/config/persistence · 7–12 d · Depends: F1 spike; live C1/C2 A2/A3/H1 · Paths: channels/, voice/, jobs/, their tests and web mic UI.**

- C1: raw-body HMAC, GET challenge, exact allowlist identity, durable unique provider/message inbox, quick 200 only after durable acceptance, retryable worker/outbox, bound approval buttons, ≤600-character text. Test forged/replayed webhooks before live sending.
- Start Pipecat/Python/WebRTC and 1.2 s feasibility spike after F1. Human starts Meta business/number/template setup early; report compatibility/timing evidence before promising the final latency.
- C2: authenticated voice sessions bound to user/conversation, VAD/STT/TTS streaming, barge-in/cancellation/stale-audio suppression. Read action details; “yes” confirms only one outstanding action within an expiring window. Other replies cancel confirmation.
- Derive spoken amounts from verified structured facts. Channel formatting cannot change numbers or drop required warnings; verify again if new model-generated content is introduced. Filler audio does not count toward meaningful-answer latency.
- C3: nightly anomaly scan, 09:00 IST brief, weekly ops report. Durable `(job, local_date, outlet)` claim, completion/retry state and delivery outbox prevent duplicate sends across workers/restarts. APScheduler triggers; database holds durable work.
- **Accept:** webhook restart/replay/signature tests, job concurrency/crash tests, WhatsApp approval recording; ≥20 fixed voice utterances with raw stage timings and p50 ≤1.2 s/p95 ≤2 s to meaningful verified audio. Misses are recorded, not hidden by filler.

### I1–I2 — Transactional CSV onboarding

**Codex I1 backend; Claude I2 wizard · 5–7 d combined · Depends: F2, private-data boundary design, F1 import contract · Paths: importer/, API/schema integration, web wizard.**

- Owner-only upload/preview/mapping/validation/commit with durable lifecycle, ownership, size/row limits and staging TTL. Router sees only headers + ≤5 redacted sample rows, treated as untrusted data. Confirm mapping explicitly.
- Ask about ambiguous DD/MM versus MM/DD; validate timezone/overnight intervals, missing versus invalid clock-outs, required fields, overlaps, negatives, duplicates and foreign references. Fuzzy matching suggests, never silently merges.
- Commit employees/shifts/attendance plus recomputed payslips in one tenant transaction, revalidating staged version. Commit request identity prevents duplicates. Invalidate read cache.
- Wizard: edit mapping → report → explicit commit → stored result/recovery. Supply two messy samples.
- **Accept:** invalid upload writes no business rows; ownership/date ambiguity/rollback/retry/duplicate commit tests; safe downloadable CSV handling; existing tenant preserved; fresh-outlet human onboarding recording ≤10 min.

### L1 — Launch evidence

**Claude drafts; Codex validates claims; human publishes personal materials · 3–4 d · Depends: M4, M5, I2 · Paths: README and launch docs/artifacts.**

- README live/demo/dashboard links, architecture, tested install commands, screenshots and results generated from report IDs. Blog from iteration log; 90-second demo covers pay → approval → channels → evals.
- Prepare MCP registry/install material; time a clean-clone setup using README only.
- Human updates resume with measured results and approves/sends outreach. Agents can draft; this plan does not authorize sending DMs/publishing personal materials.
- **Accept:** linked evidence and explicit review of every spec §17 checkbox, including resume/outreach. Deployment alone is not full completion.

## 5. Milestone gates and working rules

| Milestone | Evidence |
|---|---|
| M1 | T1/T2; deterministic seed; 12 tools; ≥90% unit tool coverage; Claude Desktop example. |
| M2 | A1–A3/W2 and deploy slice of H2; live verified answer; approval + new pay; trace; server-side memory. |
| M3 | E1–E4/R1; 200 cases; human-calibrated judge; three runs; dashboard/report publication; smoke gate/log entry. |
| M4 | H1/H2; full quality/text/cost targets; four-model comparison; failure analysis; API/agent/security tests. |
| M5 | C1–C3; WhatsApp recording; voice p50/p95 from traces; durable jobs and weekly report. |
| M6 | I1/I2/L1; import timing; fresh clone; README/video/blog/MCP; §17 audited. |

- Each PR includes meaningful focused tests with fake providers; use disposable services for DB/HTTP checks. Do not defer API/agent tests to M4.
- Use separate worktrees and disposable databases. No two agents may reset/seed the same DB.
- Integration needs green deterministic checks and available, compatible live smoke evidence. Missing credentials are a named blocker, never a silent pass; independent fixture work continues.
- Measure coverage for `mcp_server/tools/` explicitly; aggregate server/core coverage is not the unit-tool metric. Keep unit and integration coverage separate.
- Every handoff includes git SHA, commands/outcomes, migration effects, contract changes and limitations.

## 6. Decisions and human inputs

| Input | Working rule | Due |
|---|---|---|
| Staff checklist access | Manager/owner only under spec §1; staff support needs explicit spec change. No staff approval. | T2 |
| Handbook/tool parity | Enforce 24 h swap notice and weekly 50% deduction cap; document other policy-only rules. | T1/T2 |
| Speculative answer streaming | Progress plus verified answer chunks initially; record correctness/latency tradeoff. | F1/A3 |
| Hosting/report storage | Propose one concrete deployment after runtime needs are known; account/budget choice before deploy; test actual report synchronization. | H2 |
| SDK/model versions/prices | Verify access/current official APIs during implementation; lock dependencies. Config IDs are candidates. | F0/W1 |
| Credentials/repo/tracing | Human supplies through secret stores; verify without printing values. | F0/integration |
| Judge labels | Human labels 40 saved answers; Claude prepares packet. | E3 |
| Meta/voice setup | Human controls business/number/template and live-contact permissions. | Start early |
| Personal publication/outreach | Drafts can be prepared; human approves external sending/publication. | L1 |

Next: **Codex F0/F1; Claude reviews F1, then implements E1/W1 against frozen fixtures.** Copy the starting prompts from the work board.
