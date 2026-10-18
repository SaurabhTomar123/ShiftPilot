"""LangGraph agent: guard -> router -> executor (tool loop) -> verifier -> responder.

Approvals are NOT an LLM step: propose_* tools create pending actions; the API's
/actions/{id}/approve executes them. TODO(M2): add a LangGraph `interrupt` after propose_* so a
conversation can resume with the execution result, plus a Postgres checkpointer for memory.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from agent import guard, verifier
from agent.llm import Usage, complete
from agent.tools_bridge import ToolBridge, compact, openai_tool_schemas
from core.auth import Caller
from core.config import settings

PROMPTS = Path(__file__).with_name("prompts")
SYSTEM_PROMPT_VERSION = "system_v1"
ROUTER_PROMPT_VERSION = "router_v1"

INTENT_TOOLS: dict[str, list[str]] = {
    "lookup": ["find_employee", "get_shifts", "get_attendance", "get_checklist"],
    "pay_explain": ["find_employee", "explain_payslip", "get_payroll_summary"],
    "anomaly": ["list_anomalies", "find_employee", "get_attendance", "explain_payslip"],
    "action": ["find_employee", "propose_deduction", "get_shifts", "explain_payslip"],
    "policy": ["search_policy"],
    "smalltalk": [],
    "out_of_scope": [],
}
SAFE_FALLBACK = ("I couldn't verify every number in my answer, so I won't guess. "
                 "Here is what the records show:")


class AgentState(TypedDict, total=False):
    caller: Caller
    user_name: str
    outlet_name: str | None
    channel: str
    history: list[dict[str, Any]]  # prior turns, OpenAI message format
    user_input: str
    flags: list[str]
    intent: str
    messages: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    tool_outputs: list[Any]
    pending_action_ids: list[str]
    answer: str
    ungrounded: list[str]
    usage: Usage
    bridge: ToolBridge


def _system_prompt(state: AgentState) -> str:
    cfg = settings()
    today = cfg.today()
    caller = state["caller"]
    outlet_line = f" at {state['outlet_name']}" if state.get("outlet_name") else ""
    return (PROMPTS / f"{SYSTEM_PROMPT_VERSION}.md").read_text(encoding="utf-8").format(
        today=today.isoformat(), weekday=today.strftime("%A"), user_name=state.get("user_name", ""),
        role=caller.role.value, outlet_line=outlet_line)


def guard_node(state: AgentState) -> AgentState:
    text, flags = guard.check(state["user_input"])
    return {"user_input": text, "flags": flags}


def router_node(state: AgentState) -> AgentState:
    prompt = (PROMPTS / f"{ROUTER_PROMPT_VERSION}.md").read_text(encoding="utf-8")
    recent = [m for m in state.get("history", []) if m["role"] in {"user", "assistant"}][-4:]
    resp = complete([{"role": "system", "content": prompt}, *recent,
                     {"role": "user", "content": state["user_input"]}],
                    model=settings().router_model, json_mode=True, usage=state["usage"],
                    metadata={"node": "router"})
    try:
        intent = json.loads(resp.choices[0].message.content or "{}").get("intent", "lookup")
    except json.JSONDecodeError:
        intent = "lookup"
    return {"intent": intent if intent in INTENT_TOOLS else "lookup"}


def executor_node(state: AgentState) -> AgentState:
    schemas = openai_tool_schemas()
    names = INTENT_TOOLS.get(state["intent"], list(schemas))
    tools = [schemas[n] for n in names if n in schemas] or None
    messages: list[dict[str, Any]] = [{"role": "system", "content": _system_prompt(state)},
                                      *state.get("history", []),
                                      {"role": "user", "content": state["user_input"]}]
    calls: list[dict[str, Any]] = []
    outputs: list[Any] = []
    pending: list[str] = []
    bridge = state["bridge"]
    for _step in range(settings().max_agent_steps):
        resp = complete(messages, tools=tools, usage=state["usage"],
                        metadata={"node": "executor", "intent": state["intent"]})
        msg = resp.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))
        if not getattr(msg, "tool_calls", None):
            return {"messages": messages, "answer": msg.content or "", "tool_calls": calls,
                    "tool_outputs": outputs, "pending_action_ids": pending}
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            started = time.perf_counter()
            result = bridge.call(state["caller"], tc.function.name, args)
            calls.append({"name": tc.function.name, "args": args,
                          "ok": "error" not in result,
                          "latency_ms": int((time.perf_counter() - started) * 1000)})
            outputs.append(result)
            if isinstance(result.get("data"), dict) and result["data"].get("pending_action_id"):
                pending.append(str(result["data"]["pending_action_id"]))
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": compact(result)})
    return {"messages": messages, "tool_calls": calls, "tool_outputs": outputs,
            "pending_action_ids": pending,
            "answer": "That took too many steps. Could you narrow the question?"}


def verifier_node(state: AgentState) -> AgentState:
    bad = verifier.ungrounded_numbers(state.get("answer", ""), state.get("tool_outputs", []))
    if not bad:
        return {"ungrounded": []}
    # One regeneration with explicit feedback, no tools.
    messages = [*state["messages"], {"role": "user", "content": (
        f"[verifier] These numbers are not in any tool result: {', '.join(bad)}. Rewrite the "
        "answer using only figures exactly as the tools returned them.")}]
    resp = complete(messages, usage=state["usage"], metadata={"node": "verifier"})
    answer = resp.choices[0].message.content or ""
    still_bad = verifier.ungrounded_numbers(answer, state.get("tool_outputs", []))
    if still_bad:
        answer = SAFE_FALLBACK + "\n" + compact({"tool_results": state.get("tool_outputs", [])},
                                                 limit=1500)
    return {"answer": answer, "ungrounded": still_bad}


def responder_node(state: AgentState) -> AgentState:
    """Channel formatting. TODO(M5): WhatsApp (<=600 chars, buttons), voice (spoken numbers)."""
    answer = state.get("answer", "").strip()
    if state.get("channel") == "whatsapp" and len(answer) > 1500:
        answer = answer[:1500] + "…"
    return {"answer": answer}


def build_graph() -> Any:
    g = StateGraph(AgentState)
    g.add_node("guard", guard_node)
    g.add_node("router", router_node)
    g.add_node("executor", executor_node)
    g.add_node("verifier", verifier_node)
    g.add_node("responder", responder_node)
    g.set_entry_point("guard")
    g.add_edge("guard", "router")
    g.add_edge("router", "executor")
    g.add_edge("executor", "verifier")
    g.add_edge("verifier", "responder")
    g.add_edge("responder", END)
    return g.compile()


GRAPH = build_graph()
