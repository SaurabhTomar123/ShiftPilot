# ShiftPilot — Requirements Spec v1.0

> AI ops agent for restaurants: managers, owners and staff ask questions and request actions in plain language (web, voice, WhatsApp). The agent answers from real data through an MCP tool server, never does arithmetic itself, and every change needs human approval. Quality is proven by a public eval suite.

## 0. Goals and success metrics

**Goals:** (1) answer operational questions accurately from data, (2) take actions safely with approval, (3) prove quality with evals, model comparison and failure analysis, (4) demoable by a stranger in under 30 seconds.

**Out of scope:** real payroll disbursement, bank integrations, statutory filing, native mobile apps.

| Metric | Target |
|---|---|
| Task success (eval set) | ≥ 92% |
| Tool-call accuracy | ≥ 95% |
| Numeric accuracy on pay explanations | 100% |
| Security / red-team pass rate | 100% |
| Text latency | p50 ≤ 3 s, p95 ≤ 6 s |
| Voice time to first audio | p50 ≤ 1.2 s |
| Cost per conversation | ≤ ₹0.50 average |
| CSV onboarding of a new outlet | ≤ 10 min |

## 1. Users and permissions

| Role | Can see | Can request |
|---|---|---|
| Owner | All outlets in the org | Everything; approves high-impact actions |
| Manager | Own outlet only | Shift swaps, deductions ≤ ₹2,000, checklist updates |
| Staff | Own shifts, attendance and payslips only | Swap requests for own shifts (manager approves) |

- Enforced in the tool layer **and** by Postgres RLS — never by the prompt alone.
- Deductions above ₹2,000 need the owner.
- Within their authority, a requester confirms their own action explicitly (that is the human-in-the-loop). Anything beyond their authority needs someone who has it. Staff never approve.

## 2. Data model (Postgres)
organizations · ot_rules · outlets · employees (aliases[], job_role, pay_type, hourly_rate) · rate_history · users (phone, role) · shifts (label opening/mid/closing, status, version) · attendance (clock_in/out) · tips · tip_allocations · pay_periods (weekly, open/locked/paid) · deductions (advance/meal/uniform/damage/pf/esi/tds) · payslips (totals + full detail jsonb) · checklists · checklist_items · policy_docs · policy_chunks (vector(1536)) · pending_actions (args, status, required_approver_role, idempotency_key, expires_at, result) · audit_log (append-only) · conversations · messages.

Every table carries `org_id`; RLS policy `org_id = current_setting('app.org_id')`; the app connects as a non-superuser role.

## 3. Synthetic data
1 org, 3 outlets (café, QSR, cloud kitchen), 60 staff incl. near-duplicate names (Ravi Kumar / Ravi K), 8 weeks of shifts, attendance, tips, deductions, payslips. Planted anomalies: 6 missed clock-outs, 4 OT spikes (>12 h), 3 duplicate deductions, 2 tip-allocation mismatches, 1 mid-period rate change. Deterministic from a seed; writes `seed/ground_truth.json`. Reset in < 20 s. Sample handbook policy.

## 4. MCP server `restaurant-ops`
Identity always from the session (JWT over HTTP; configured demo user over stdio), never from LLM args. Pydantic-validated inputs; output envelope `{data, warnings, source_ids}`; every call audited; **all arithmetic inside tools**.

| # | Tool | Kind |
|---|---|---|
| 1 | find_employee (fuzzy + aliases, `needs_disambiguation`) | read |
| 2 | get_shifts | read |
| 3 | get_attendance (flags: late, missing_clock_out, early_leave, over_12_hours) | read |
| 4 | explain_payslip (line items + reconciled diff vs previous period) | read |
| 5 | get_payroll_summary | read |
| 6 | list_anomalies | read |
| 7 | get_checklist | read |
| 8 | search_policy (citations) | read |
| 9 | propose_shift_swap (overlap, 10 h rest, same role) | propose |
| 10 | propose_shift_reassign | propose |
| 11 | propose_deduction (limits, duplicate warning) | propose |
| 12 | propose_checklist_update | propose |

Execution is **not** an LLM tool: only `/actions/{id}/approve`, which re-checks authority, expiry, optimistic locking and idempotency. Pending actions expire after 30 min. ≥ 90% unit coverage on tools.

## 5. Agent (LangGraph)
Nodes: **guard** (PII/injection/limits) → **router** (small model; intent + date extraction) → **executor** (main model, ReAct, intent-scoped tools, ≤ 8 steps) → **disambiguate** (ask when names/dates are ambiguous) → **verifier** (every number must appear in tool output; one regeneration, then safe fallback) → **approval interrupt** → **responder** (per-channel formatting).
Memory: last 20 turns + resolved entities, Postgres checkpointer. Models via LiteLLM: router (small), main, fallback on another provider; prompt caching; 60 s read cache. Prompts versioned in `agent/prompts/` and logged per trace.

## 6. Policy RAG
Markdown/PDF chunked by heading (~400 tokens, 60 overlap). Hybrid retrieval (pgvector cosine + FTS, reciprocal rank fusion), top 5, optional reranker. Must cite `[Doc › Section]`; low confidence → "not found in your policies". Metrics: hit@5, faithfulness, citation accuracy.

## 7. Security
JWT auth + demo persona tokens; WhatsApp phone allowlist · role checks + RLS + approver check · tenant isolation · PII redaction in logs/traces · injection red-team suite (direct, indirect, role-play, encoded) · webhook signature verification · 30 msg/min, 20k tokens/conv, 8 steps · secrets only in env · append-only audit log. See `docs/threat-model.md`.

## 8. Channels
- **Web chat (required):** streaming, persona switcher, "Show work" panel (tool, args, result, latency, cost), approval cards, reset sandbox, 6 suggested prompts, no signup.
- **Voice (browser):** Pipecat, Silero VAD, Deepgram STT, Cartesia/ElevenLabs TTS, barge-in, filler line for slow tools, spoken read-back + "yes" to confirm, per-stage latency. p50 ≤ 1.2 s, p95 ≤ 2 s.
- **WhatsApp:** Cloud API webhook, Approve/Reject buttons, ≤ 600-char messages, template for the morning brief.

## 9. Admin panel
Conversations · Approvals queue · Eval dashboard (trend, model matrix, failure categories, drill-down) · Audit log · Data import.

## 10. Evals
- `evals/golden_set.jsonl`, target 200 cases: lookup 50, pay explanation 35, actions 30, policy 25, disambiguation/multi-turn 20, security 25, messy input 15.
- Deterministic graders (tools + args, facts from ground truth, refusal, pending action, clarification, no-leak, grounding) + LLM-as-judge from a different model family, calibrated on 40 hand labels (≥ 85% agreement). 3 runs per case, mean ± stdev.
- Metrics: task success, tool accuracy, argument accuracy, numeric accuracy, faithfulness, refusal correctness, security pass rate, p50/p95 latency, ₹/case.
- Smoke (every PR, < 4 min) and full (nightly). **Gate:** task success −3 pts, any security failure, numeric accuracy < 100%, or p95 +25% fails the build.
- Model comparison across ≥ 4 models; failure taxonomy; `evals/ITERATION_LOG.md`.

## 11. Bring-your-own-data
CSV upload, LLM-suggested column mapping (user confirms), validation report, transactional import, payslip generation. < 10 min, recorded.

## 12. Reliability
Tool timeout 5 s, LLM 20 s, 2 retries with backoff on 429/5xx, provider fallback + circuit breaker, idempotent approvals, optimistic locking, graceful "nothing was changed" errors with trace id, idempotent background jobs.

## 13. Observability
Langfuse trace per message with spans per node/tool/LLM call; tags: org, role, channel, intent, prompt version, model; cost, tokens, latency, tool error rate, approval rate, fallback rate; weekly ops report.

## 14. API
`POST /auth/demo-token` · `POST /chat` · `POST /chat/stream` (SSE) · `GET /conversations/{id}` · `GET /actions` · `POST /actions/{id}/approve|reject` · `POST /webhooks/whatsapp` · `POST /voice/session` · `POST /import/csv`, `/import/{id}/commit` · `GET /evals/runs[/{id}]` · `POST /sandbox/reset` · `GET /healthz`

## 15. Non-functional
Python 3.12+, ruff, mypy strict (core, mcp_server), pytest; TypeScript strict, ESLint, Playwright (5 E2E flows); `docker compose up` runs the stack; demo cold start < 10 s; mobile-friendly, keyboard accessible.

## 16. Milestones
| Milestone | Done when |
|---|---|
| M1 Data + tools | seed works; all 12 tools tested; Claude Desktop answers "who's closing Friday" via MCP |
| M2 Agent + web | chat, streaming, show-work, approvals, role switch; deployed URL; Langfuse traces |
| M3 Evals | 200 cases; calibrated judge; smoke gate in CI; nightly full; dashboard; first iteration-log entry |
| M4 Quality | §0 targets hit; model comparison; failure analysis; red-team 100% |
| M5 Channels | browser voice p50 ≤ 1.2 s; WhatsApp approval demo recorded |
| M6 Onboarding + launch | CSV import < 10 min on video; README, video, blog, MCP listing |

## 17. Definition of done
- [ ] A stranger opens the live link, picks a role, gets a correct answer in < 30 s
- [ ] Eval dashboard is public; README numbers match the latest run
- [ ] No answer contains a number that isn't in tool output
- [ ] Every write went through approval and is in the audit log
- [ ] `docker compose up` works from a clean clone
- [ ] Resume updated with real metrics; demo video in outreach DMs
