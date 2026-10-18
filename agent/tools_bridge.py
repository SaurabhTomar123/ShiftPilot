"""How the agent reaches the restaurant-ops tools.

InProcessBridge calls the same functions the MCP server exposes, with the same auth and audit
path, without a network hop (fast for evals and local dev). McpHttpBridge is the production path.
Both expose identical tool schemas, taken from the MCP server itself.
"""

from __future__ import annotations

import asyncio
import json
from functools import lru_cache
from typing import Any, Protocol

from core.auth import Caller, PermissionDenied
from core.jsonable import jsonable
from db.session import tenant_session
from mcp_server import server as mcp_srv
from mcp_server.context import audit
from mcp_server.queries import NotFound
from mcp_server.tools import read, write

IMPLEMENTATIONS = {
    "find_employee": read.find_employee,
    "get_shifts": read.get_shifts,
    "get_attendance": read.get_attendance,
    "explain_payslip": read.explain_payslip,
    "get_payroll_summary": read.get_payroll_summary,
    "list_anomalies": read.list_anomalies,
    "get_checklist": read.get_checklist,
    "search_policy": read.search_policy,
    "propose_deduction": write.propose_deduction,
}


@lru_cache
def openai_tool_schemas() -> dict[str, dict[str, Any]]:
    """Tool definitions in OpenAI/LiteLLM format, generated from the MCP server's own schemas."""
    tools = asyncio.run(mcp_srv.mcp.list_tools())
    return {t.name: {"type": "function",
                     "function": {"name": t.name, "description": t.description or "",
                                  "parameters": t.input_schema}} for t in tools}


class ToolBridge(Protocol):
    def call(self, caller: Caller, name: str, args: dict[str, Any]) -> dict[str, Any]: ...


class InProcessBridge:
    def call(self, caller: Caller, name: str, args: dict[str, Any]) -> dict[str, Any]:
        fn = IMPLEMENTATIONS.get(name)
        if fn is None:
            return {"error": "unknown_tool", "message": name}
        args = {k: v for k, v in args.items() if v is not None}
        try:
            with tenant_session(caller) as s:
                result = fn(s, caller, **_coerce(name, args))
            audit(caller, name, args, "ok", channel="agent")
            return result
        except PermissionDenied as exc:
            audit(caller, name, args, "denied", channel="agent")
            return {"error": "permission_denied", "message": str(exc)}
        except (ValueError, NotFound, TypeError) as exc:
            audit(caller, name, args, "error", channel="agent")
            return {"error": "invalid_request", "message": str(exc)}


def _coerce(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """LLM sends JSON strings; turn ISO dates into date objects like FastMCP would."""
    from datetime import date

    out = {}
    for k, v in args.items():
        if isinstance(v, str) and k in {"date_from", "date_to", "period_date", "day"}:
            out[k] = date.fromisoformat(v)
        else:
            out[k] = v
    return out


class McpHttpBridge:
    """TODO(M2): call the server over Streamable HTTP with the caller's JWT:
        from mcp.client.streamable_http import streamablehttp_client
        from mcp import ClientSession
        headers={"Authorization": f"Bearer {core.tokens.issue(caller)}"}
    Keep one session per conversation; map CallToolResult.structuredContent to a dict."""

    def call(self, caller: Caller, name: str, args: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


def compact(result: dict[str, Any], limit: int = 12000) -> str:
    """Serialize a tool result for the model, truncating huge lists."""
    text = json.dumps(jsonable(result), ensure_ascii=False)
    if len(text) <= limit:
        return text
    return text[:limit] + '..."[truncated: narrow the date range or filters]"'
