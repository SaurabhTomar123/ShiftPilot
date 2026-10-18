"""Resolve who is calling the MCP server, plus the audit trail."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from core.auth import Caller, PermissionDenied, Role
from core.config import settings
from core.redact import redact
from core.tokens import verify
from db.models import AuditLog, User
from db.session import admin_session, tenant_session


def caller_for_phone(phone: str) -> Caller:
    """Identity lookup spans tenants, so it uses the admin connection with an exact phone match.
    Everything after this runs under RLS as the resolved caller."""
    with admin_session() as s:
        user = s.scalars(select(User).where(User.phone == phone, User.is_active)).first()
        if user is None:
            raise PermissionDenied("Unknown or inactive user.")
        return Caller(user_id=str(user.id), org_id=str(user.org_id), role=Role(user.role),
                      outlet_id=str(user.outlet_id) if user.outlet_id else None,
                      employee_id=str(user.employee_id) if user.employee_id else None)


def resolve_caller(ctx: Any) -> Caller:
    """HTTP transport: `Authorization: Bearer <jwt>` issued by the API (signature-verified;
    a header alone is never trusted).
    stdio transport (Claude Desktop): no headers, so act as MCP_DEMO_USER_PHONE."""
    headers = getattr(ctx, "headers", None)
    if headers is not None:
        auth = headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            raise PermissionDenied("Missing bearer token.")
        return verify(auth.split(" ", 1)[1])
    return caller_for_phone(settings().mcp_demo_user_phone)


def audit(caller: Caller, tool: str, args: dict[str, Any], outcome: str,
          channel: str = "mcp", trace_id: str | None = None) -> None:
    with tenant_session(caller) as s:
        s.add(AuditLog(id=uuid.uuid4(), org_id=uuid.UUID(caller.org_id),
                       actor_user_id=uuid.UUID(caller.user_id), channel=channel, tool=tool,
                       args_redacted=redact({k: str(v) for k, v in args.items()}),
                       outcome=outcome, trace_id=trace_id))
