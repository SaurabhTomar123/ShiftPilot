"""restaurant-ops MCP server.

    python -m mcp_server.server                 # stdio (Claude Desktop / Cursor)
    python -m mcp_server.server --http          # Streamable HTTP on :8765/mcp (used by the agent)
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from datetime import date
from typing import Any

from mcp.server.mcpserver import Context, MCPServer

from core.auth import PermissionDenied
from db.session import tenant_session
from mcp_server.context import audit, resolve_caller
from mcp_server.queries import NotFound
from mcp_server.tools import read, write

mcp = MCPServer(
    "restaurant-ops",
    instructions=(
        "Tools for restaurant operations: shifts, attendance, payroll, tips, checklists and "
        "policies. All amounts are pre-computed in INR; quote them, never recalculate. "
        "Write tools only create a pending action that a human must approve."
    ),
)


def run(name: str, fn: Callable[..., dict[str, Any]], ctx: Context, **kwargs: Any) -> dict[str, Any]:
    try:
        caller = resolve_caller(ctx)
    except PermissionDenied as exc:
        return {"error": "unauthenticated", "message": str(exc)}
    try:
        with tenant_session(caller) as s:
            result = fn(s, caller, **kwargs)
        audit(caller, name, kwargs, "ok")
        return result
    except PermissionDenied as exc:
        audit(caller, name, kwargs, "denied")
        return {"error": "permission_denied", "message": str(exc)}
    except (ValueError, NotFound) as exc:
        audit(caller, name, kwargs, "error")
        return {"error": "invalid_request", "message": str(exc)}


@mcp.tool()
def find_employee(query: str, ctx: Context, outlet_id: str | None = None) -> dict[str, Any]:
    """Find employees by name or nickname. If needs_disambiguation is true, ask the user which
    person they mean before doing anything else."""
    return run("find_employee", read.find_employee, ctx, query=query, outlet_id=outlet_id)


@mcp.tool()
def get_shifts(date_from: date, date_to: date, ctx: Context, outlet_id: str | None = None,
               employee_id: str | None = None, label: str | None = None,
               job_role: str | None = None) -> dict[str, Any]:
    """Scheduled shifts in a date range (max 31 days). label: opening | mid | closing."""
    return run("get_shifts", read.get_shifts, ctx, date_from=date_from, date_to=date_to,
               outlet_id=outlet_id, employee_id=employee_id, label=label, job_role=job_role)


@mcp.tool()
def get_attendance(date_from: date, date_to: date, ctx: Context, outlet_id: str | None = None,
                   employee_id: str | None = None, only_issues: bool = False) -> dict[str, Any]:
    """Clock-in/out records with flags: late, missing_clock_out, early_leave, over_12_hours."""
    return run("get_attendance", read.get_attendance, ctx, date_from=date_from, date_to=date_to,
               outlet_id=outlet_id, employee_id=employee_id, only_issues=only_issues)


@mcp.tool()
def explain_payslip(employee_id: str, ctx: Context, period_date: date | None = None,
                    compare_to_previous: bool = True) -> dict[str, Any]:
    """An employee's payslip (latest period by default) with line items and, when comparing,
    every change from the previous period with its reason. Use for 'why is my pay lower'."""
    return run("explain_payslip", read.explain_payslip, ctx, employee_id=employee_id,
               period_date=period_date, compare_to_previous=compare_to_previous)


@mcp.tool()
def get_payroll_summary(ctx: Context, outlet_id: str | None = None,
                        period_date: date | None = None) -> dict[str, Any]:
    """Payroll totals per outlet for a pay period (managers and owners)."""
    return run("get_payroll_summary", read.get_payroll_summary, ctx, outlet_id=outlet_id,
               period_date=period_date)


@mcp.tool()
def list_anomalies(ctx: Context, outlet_id: str | None = None, period_date: date | None = None,
                   types: list[str] | None = None) -> dict[str, Any]:
    """Payroll/attendance anomalies with evidence: missing_clock_out, ot_spike,
    duplicate_deduction, tip_mismatch, rate_change_mid_period."""
    return run("list_anomalies", read.list_anomalies, ctx, outlet_id=outlet_id,
               period_date=period_date, types=types)


@mcp.tool()
def get_checklist(day: date, type: str, ctx: Context, outlet_id: str | None = None) -> dict[str, Any]:
    """Opening or closing checklist for a day, with which items are done and by whom."""
    return run("get_checklist", read.get_checklist, ctx, day=day, type=type, outlet_id=outlet_id)


@mcp.tool()
def search_policy(query: str, ctx: Context, k: int = 5) -> dict[str, Any]:
    """Search the employee handbook and policies. Cite the returned `citation` in answers."""
    return run("search_policy", read.search_policy, ctx, query=query, k=k)


@mcp.tool()
def propose_deduction(employee_id: str, type: str, amount: str, note: str, ctx: Context,
                      period_date: date | None = None) -> dict[str, Any]:
    """PROPOSE a deduction (advance, meal, uniform, damage, pf, esi, tds). Creates a pending
    action only; nothing changes until a human approves it."""
    return run("propose_deduction", write.propose_deduction, ctx, employee_id=employee_id,
               type=type, amount=amount, note=note, period_date=period_date)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--http", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.http:
        mcp.run(transport="streamable-http", port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
