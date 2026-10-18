# ShiftPilot implementation contracts

> **Historical: v1 contracts only.** Scheduling v2 contracts are produced by task B0.3 in [SCHEDULING_V2_TASKS.md](SCHEDULING_V2_TASKS.md) under `contracts/v2/`. The ownership references below ("the work board defines owners") point to the superseded v1 board. Reuse individual technical rules only where the v2 roadmap explicitly adopts them.

**Status: proposed target behavior, 16 October 2026.** These are implementation decisions, not a description of the current API. F1 must create machine-readable schemas and fixtures before parallel consumers rely on them.

The [plan](DEV_PLAN.md) defines acceptance and the [work board](PARALLEL_WORK.md) defines owners. Product-spec conflicts require an explicit decision. Contract changes update schemas, fixtures and provider/consumer tests together.

## 1. Identity, data and time

- Identity comes from authenticated context, never an LLM argument. Every resource check combines organization with role/outlet/user ownership. Organization RLS alone does not authorize access to a same-org peer's conversation or payslip.
- Conversations are private to their originating user by default. Manager/owner action approval does not grant access to another user's chat. Broader conversation administration needs a separately specified audited permission.
- Managers access own-outlet actions/audit; owners their organization. Staff access sanitized own-request status, never approve. Authorize every terminal-result replay before returning data.
- Persona change starts a new user-scoped conversation and clears UI caches. Demo tokens/reset exist only in an allowlisted synthetic environment; arbitrary phone lookup must not mint private-data identities.
- Money is a decimal string, e.g. `"2000.00"`, with currency INR where needed. Arithmetic stays in deterministic tools. No binary-float round trips; reject non-finite/invalid amounts.
- Store instants in UTC with offsets; evaluate restaurant dates/rest in outlet timezone (Asia/Kolkata in demo). Use an injectable clock; record frozen eval/demo clock in reports.
- Pay weeks are Monday–Sunday. Working demo rule: “this Friday” means Friday in the current ISO week, matching the closing-Friday fixture; “next Friday” means the following ISO week's Friday. Explicit dates override relative phrases. “Kal” without directional context needs clarification. Update fixtures if the rule changes.
- Seed future roster separately from historical attendance/pay. Swap starts must both be ≥24 h after the clock at proposal and execution; reassignment needs future status but no invented notice requirement.

## 2. HTTP surfaces

F1 freezes exact types/examples. Lists use stable cursor plus bounded limit. Validate IDs/filters; inaccessible IDs return generic 404 consistently. Document malformed-input 422, access denial and state-conflict responses separately.

| Surface | Target behavior | Provider / consumer |
|---|---|---|
| POST /auth/demo-token | Allowlisted synthetic persona → token and caller/outlet display metadata. | Codex / Claude web |
| POST /chat; POST /chat/stream | `{message, conversation_id?, client_request_id}`; no client history/caller/tool results. | Codex / web, channel service, eval adapter |
| GET /conversations; GET /conversations/{id} | Own summaries / ordered messages and pending turn state; paginated. | Codex / Claude web |
| GET /actions | Authorized filtered action cards, including complete warnings/expiry and viewer permissions. | Codex / Claude web |
| POST /actions/{id}/approve or /reject | Durable canonical decision; repeated/opposite decisions cannot reverse terminal state. | Codex / web, channels |
| GET /audit | Owner/manager scoped, redacted, paginated; tool/outcome filters. | Codex / Claude web |
| GET /evals/runs; GET /evals/runs/{id} | Sanitized synthetic reports; opaque allowlisted IDs, never arbitrary paths. | Codex / Claude dashboard |
| POST /sandbox/reset | Synthetic tenant only; serialized reset, data-generation bump and memory/cache invalidation. | Codex / Claude web |
| POST /import/csv | Owner upload → import ID, headers/preview/staging state, no business writes. | Codex / Claude wizard |
| GET /import/{id}; POST /import/{id}/mapping; POST /import/{id}/validate | Owner-scoped status; explicit mapping; validation errors/warnings and staged version. | Codex / Claude wizard |
| POST /import/{id}/commit | Staged version + commit request ID → stored counts/result; atomic business transaction. | Codex / Claude wizard |
| WhatsApp GET/POST webhook; POST /voice/session | Verified provider webhook / authenticated session signaling; thin routes call shared services. | Codex routes / Claude adapters |

Every response has trace_id. Chat additionally has conversation_id, turn_id, status, canonical answer, tool-call summaries, pending cards, usage, actual models and prompt versions. Errors use a consistent `error` envelope with code, message, trace_id, retryable and action_status when applicable; no provider exception dump.

Chat retry identity is `(org, user, client_request_id)`. Reuse returns the same conversation/turn; different content with the same key conflicts. Initially return a retryable busy conflict for a second active turn in a conversation. Coordination must work across processes, not just a module-level lock.

## 3. Proposals, decisions and checkpoint recovery

Action card: id, tool, summary, warnings, status, required_approver_role, can_approve, expires_at, created_at and version. `can_approve` is a viewer projection, never an authorization token. Checklist storage needs a version/precondition too.

```text
pending -> executed | rejected | expired | failed
```

All terminal states are immutable. Decision envelope: action_id, status, result, idempotent, trace_id and resume_status (pending/delivered/failed narration); conversation_id only if visible to the caller. Narration failure cannot change executed status.

- TTL: 30 minutes. Mutation, terminal status, decision audit and unique resume-outbox entry commit together. Failed execution rolls back business writes but preserves failed status/audit.
- Retry identity includes stable turn/tool-call request ID plus database uniqueness. Permanent business-argument hashes alone conflate retries with legitimate later identical requests.
- Scheduling serializes affected employees in stable order, then locks/version-checks shifts, reloads neighboring assignments and updates atomically. Every writer follows the same protocol; shift versions alone miss concurrent neighboring changes.
- Deduction cap checks serialize per employee/pay period. Executor results contain computed monetary evidence, not model-generated totals.
- One pending action per conversation initially. Persist action/result/thread link before a separate interrupt node. A replayed node must not recreate a proposal before calling interrupt.
- Checkpoint JSON-compatible messages/evidence/IDs/counters/versions. Inject authenticated caller, bridge, sessions, event sinks and mutable usage machinery at runtime.
- Namespace thread by org/conversation and authorize before invoking/resuming. Dedicated least-privilege checkpoint storage does not automatically inherit domain RLS. Test cross-thread isolation.
- Approver identity authorizes execution; original requester context controls narration visibility. Managers may decide staff requests without reading staff conversations.
- Resume outbox is at-least-once with unique action-result identity. Deduplicate graph handling and message insertion; recover crash between commit and resume. Do not claim exactly-once delivery without testing those boundaries.

## 4. SSE and grounding

Use authenticated POST fetch with streamed response parsing. Native EventSource does not supply the required POST/body/header flow.

Events carry increasing id, schema_version, conversation_id, turn_id and trace_id. F1 fixtures cover these payloads:

| Event | Data |
|---|---|
| node | Node name; started/completed. |
| tool_start | call_id, name, authorized/redacted args. |
| tool_end | Matching call_id, ok, latency, authorized result projection or typed error. |
| approval | Complete card and persisted awaiting-approval state. |
| token | Text chunk from verified canonical answer. |
| replace | Verified canonical answer for reconciliation. |
| final | Canonical answer/status/intent/models/usage/latency/prompts/pending cards. |
| error | Typed error and durable turn/action status where known. |

Exactly one final or error terminates a stream. Progress may precede verification; answer content cannot. Heartbeats prevent idle proxy timeouts. Disconnected clients reconcile persisted conversation/turn state and deduplicate IDs; initial scope need not replay every progress event. Final persisted state is authoritative.

The current verifier matches money/decimal membership, discards signs through abs and ignores many integers. This does not prove a number belongs to the right employee/period/field. Strengthen evidence to include source/entity/period/measure/signed value; test swapped entities, wrong periods, signs, integers and accepted formatting. Dates/times/policy counts need support when stated; they are not blanket exemptions to the spec.

Regenerate once, then render a safe caller-authorized evidence projection. Never dump raw tool results as fallback. Channel formatting must preserve verified facts/warnings; verify any new model-generated content again. TTS never consumes unverified drafts.

If execution committed but narration failed, report that the action completed and its reply could not be generated, with durable status/trace. “Nothing was changed” is reserved for known no-write/rejected/rollback outcomes. Unknown network outcomes trigger status lookup before mutation retry.

## 5. Evaluation definitions

Cases specify persona, clock/seed, ordered turns, per-turn assertions, optional human decisions and final database-state expectations. Keep a legacy adapter while migrating starter cases; do not silently redefine their assertions.

| Metric | Definition |
|---|---|
| Task success | All required deterministic checks and declared calibrated judge threshold when judge-required. Report deterministic and judged rates separately. |
| Tool accuracy | Precision/recall against expected/forbidden/extra calls, with explicit allowed alternative sequences and documented aggregate. Name presence alone is insufficient. |
| Argument accuracy | Correct expected fields across evaluated calls, including dates/entities; report evaluated count. |
| Numeric accuracy | Required claims match entity/period/measure, with no unsupported claims on eligible pay cases. Omitted required amount fails. Report case/claim denominators. |
| Security | All refusal/no-leak/no-write assertions; crashes are failed cases, not safe passes. |
| Retrieval/citations | Expected-section hit@5; cited sections in authorized hits; evidence-supported claims and correct abstention. |
| Latency | Text: submission to verified final, including router/tools/retries. Report per-turn and conversation distributions separately. Voice: end of utterance to first meaningful verified audio; exclude filler. |
| Cost | All turns/router/main/fallback/verifier/retries. Judge/embedding overhead separately. Unknown model pricing is unknown, not zero. Define conversation mix. |

Release targets: task ≥92%, tool ≥95%, pay numeric/security 100%, text p50 ≤3 s/p95 ≤6 s, conversation mean ≤₹0.50; voice p50 ≤1.2 s/p95 ≤2 s. Demo first-use <30 s is a separate onboarding measure.

Regression gates: task drop **greater than 3 percentage points**, any security failure, numeric <100%, p95 increase **greater than 25%**. Absolute thresholds additionally apply to M4. Missing eligible cases, required baseline or compatible metadata cannot silently pass. Before first reviewed baseline, publish explicitly ungated provisional reports and enforce absolute numeric/security checks where coverage exists.

Reports contain schema/run ID, git SHA, suite/case/seed hashes, clock, prompts/SDK versions, requested/actual families and fallbacks, pricing/FX provenance, denominators/errors and gate outcomes. Report three-run success mean ± standard deviation of per-run rates, retaining raw results. Report timeout counts and exclusion policy rather than hiding them from latency claims.

Judge gets actual evidence/context/rubric. Calibration: 40 human labels, predefined threshold, ≥85% agreement, κ, class balance and holdout disclosure. Choose a judge independent of answer-producing families, including fallback, or disclose non-independence and do not claim that requirement passed.

Stateful cases/runs/workers use isolated databases/schemas or equivalent full fixture isolation. Never reset the public demo to run evals. Public serialization allows synthetic data only; exclude private imports, credentials, tokens, phone numbers and raw private traces.

## 6. F1 fixture checklist

Create planned contracts/v1 schemas/examples for successful read, disambiguation, approval pause/execute/reject/expire/conflict, committed-action/narration failure, conversation denial, SSE rewrite/disconnect reconciliation, report missing prices/baseline and import retry. Include entity-bound signed numerical evidence.

Also freeze service protocols for turn processing, action decisions, caller lookup, inbox/outbox storage, job claims and delivery so Claude can build channel/job modules with fakes while Codex supplies persistence/routes. Codex owns providers/schema generation; Claude owns consumer verification. Both review changed semantics.
