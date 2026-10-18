# Design decisions

## 1. Tools behind MCP
The business logic lives in an MCP server (`mcp_server/`), not inside the agent. The same tools work in Claude Desktop, Cursor and our LangGraph agent, and tool schemas are generated once from the server (`agent/tools_bridge.openai_tool_schemas`). In-process calls are used for evals/local speed; the HTTP transport is used in production with the caller's JWT.

## 2. The LLM never does arithmetic
`core/payroll.py` computes every rupee and hour deterministically (Decimal, per-day rates, daily-then-weekly overtime). `diff_payslips` explains changes component by component and is checked to reconcile exactly with the net delta. The agent only quotes these numbers; `agent/verifier.py` rejects any number in an answer that no tool returned.

## 3. Writes are proposals; approval is outside the LLM
`propose_*` tools validate and create a `pending_action`. There is no "execute" tool. Execution happens only through `/actions/{id}/approve`, which re-checks authority (`core.auth.can_approve`), expiry and status. Approval is idempotent (row lock + status check), and execution runs in a savepoint so a failure never half-applies.

## 4. Authorization is deterministic and layered
1. Tool layer: role/outlet checks in `core/auth.py` on every call.
2. Database: Postgres row-level security on every table by `org_id`; the app connects as a non-superuser role (superusers bypass RLS).
3. Prompt: asks the model to refuse, but nothing depends on it.
Prompt injection can at worst make the model *ask* for data; the tools still refuse.

## 5. Model routing
A small model classifies intent and narrows the tool list; the main model plans and calls tools; a different provider is the fallback (LiteLLM `fallbacks`). The eval suite compares models on accuracy, latency and ₹/conversation.

## 6. Deterministic synthetic data
`seed/generate.py` creates the same data for a given seed, plants known anomalies and writes `ground_truth.json`. Eval expectations reference ground truth (`expected_facts_ref`) instead of hard-coding numbers, so changing the generator never silently breaks evals.

## 7. Dates
The sandbox pins "today" to the last seeded day (`DEMO_TODAY`) so "this week" is meaningful in demos and evals.
