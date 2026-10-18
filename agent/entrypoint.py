"""Single entry point used by the API, channels and the eval runner."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select

from agent.graph import GRAPH, SYSTEM_PROMPT_VERSION
from agent.llm import Usage
from agent.tools_bridge import InProcessBridge, ToolBridge
from core.auth import Caller, Role
from db.models import Outlet, User
from db.session import admin_session, tenant_session
from mcp_server.queries import as_uuid


@dataclass
class AgentResult:
    answer: str
    intent: str
    tool_calls: list[dict[str, Any]]
    pending_action_ids: list[str]
    flags: list[str]
    ungrounded: list[str]
    latency_ms: int
    tokens: int
    cost_inr: float
    prompt_version: str = SYSTEM_PROMPT_VERSION
    history: list[dict[str, Any]] = field(default_factory=list)


def _profile(caller: Caller) -> tuple[str, str | None]:
    with tenant_session(caller) as s:
        user = s.get(User, as_uuid(caller.user_id))
        outlet = s.get(Outlet, as_uuid(caller.outlet_id)) if caller.outlet_id else None
        return (user.name if user else ""), (outlet.name if outlet else None)


def run_turn(caller: Caller, user_input: str, history: list[dict[str, Any]] | None = None,
             channel: str = "web", bridge: ToolBridge | None = None) -> AgentResult:
    started = time.perf_counter()
    usage = Usage()
    name, outlet = _profile(caller)
    state = GRAPH.invoke({
        "caller": caller, "user_name": name, "outlet_name": outlet, "channel": channel,
        "history": history or [], "user_input": user_input, "usage": usage,
        "bridge": bridge or InProcessBridge(),
    })
    new_history = [*(history or []), {"role": "user", "content": user_input},
                   {"role": "assistant", "content": state.get("answer", "")}]
    return AgentResult(
        answer=state.get("answer", ""), intent=state.get("intent", ""),
        tool_calls=state.get("tool_calls", []),
        pending_action_ids=state.get("pending_action_ids", []), flags=state.get("flags", []),
        ungrounded=state.get("ungrounded", []),
        latency_ms=int((time.perf_counter() - started) * 1000), tokens=usage.tokens,
        cost_inr=round(usage.cost_inr, 4), history=new_history)


def caller_for_user(user_id: str) -> Caller:
    """Helper for scripts: build a Caller from a user id (admin lookup)."""
    with admin_session() as s:
        user = s.scalars(select(User).where(User.id == as_uuid(user_id))).one()
        return Caller(str(user.id), str(user.org_id), Role(user.role),
                      str(user.outlet_id) if user.outlet_id else None,
                      str(user.employee_id) if user.employee_id else None)
