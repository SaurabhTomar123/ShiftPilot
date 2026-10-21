"""v2 identity: bearer JWT -> Caller, capabilities per role, and synthetic demo sessions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select, text

from api.v2 import schemas as s
from api.v2.errors import ApiError
from core.auth import Caller, Role
from core.config import settings
from core.tokens import ALGORITHM, issue, verify
from db import sandbox
from db.models import Organization, User
from db.models_v2 import DemoSandbox
from db.session import admin_session, tenant_session
from seed.world import uid

bearer = HTTPBearer(auto_error=False)

CAPABILITIES: dict[Role, list[s.Capability]] = {
    Role.OWNER: [
        "view_all_outlets",
        "manage_employees",
        "edit_demand",
        "generate",
        "publish",
        "view_costs",
        "approve_cross_outlet",
    ],
    Role.MANAGER: ["manage_employees", "edit_demand", "generate", "publish", "view_costs"],
    Role.STAFF: ["view_own_schedule", "report_own_absence"],
}
DEMO_PERSONAS = {"owner": "owner", "manager": "manager_indiranagar", "staff": "staff_ravi"}


def current_caller(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> Caller:
    if credentials is None:
        raise ApiError("unauthenticated", "Sign in to continue.")
    try:
        return verify(credentials.credentials)
    except jwt.ExpiredSignatureError as exc:
        raise ApiError("unauthenticated", "Your session has expired. Sign in again.") from exc
    except Exception as exc:
        raise ApiError("unauthenticated", "Sign in to continue.") from exc


CallerDep = Annotated[Caller, Depends(current_caller)]


def require(caller: Caller, capability: s.Capability) -> None:
    if capability not in CAPABILITIES[caller.role]:
        raise ApiError("permission_denied", "You do not have permission to do this.")


def me(caller: Caller) -> s.Me:
    with tenant_session(caller) as session:
        user = session.get(User, uuid.UUID(caller.user_id))
        org = session.get(Organization, uuid.UUID(caller.org_id))
        if user is None or org is None or not user.is_active:
            raise ApiError("unauthenticated", "This account is no longer active.")
        return s.Me(
            user_id=user.id,
            org_id=org.id,
            org_name=org.name,
            display_name=user.name,
            role=caller.role.value,
            outlet_id=uuid.UUID(caller.outlet_id) if caller.outlet_id else None,
            employee_id=uuid.UUID(caller.employee_id) if caller.employee_id else None,
            timezone=org.timezone,
            capabilities=CAPABILITIES[caller.role],
        )


SANDBOX_TTL = timedelta(hours=2)
MAX_SANDBOXES = 200  # live public sandboxes; beyond this new visitors wait (429)


def demo_session(persona: str, sandbox_id: uuid.UUID | None = None) -> s.DemoSession:
    """Synthetic demo only (B6.2). Each visitor gets an isolated copy of the template org (a sandbox,
    purged by the retention job after SANDBOX_TTL); sending sandbox_id back switches persona inside it.
    The user is looked up by its mapped seed ID inside that sandbox, so this can never issue a token for
    another tenant's user."""
    if not settings().demo_sessions_enabled:
        raise ApiError("permission_denied", "Demo sessions are not available on this deployment.")
    template = uid("org", settings().demo_org_key)
    with admin_session() as session:
        now = session.execute(text("SELECT now()")).scalar_one()
        if sandbox_id is not None:
            box = session.get(DemoSandbox, sandbox_id)
            if box is None or box.expires_at <= now:
                raise ApiError("not_found", "This demo has expired. Start a new one.")
        else:
            session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('demo-sandboxes', 0))"))
            live = session.scalar(
                select(func.count()).select_from(DemoSandbox).where(DemoSandbox.expires_at > now)
            )
            if (live or 0) >= MAX_SANDBOXES:
                raise ApiError(
                    "rate_limited",
                    "The demo is busy right now. Try again in a minute.",
                    retryable=True,
                    headers={"Retry-After": "60"},
                )
            if session.get(Organization, template) is None:
                raise ApiError("not_found", "The demo organization is not loaded. Run python -m seed.v2.")
            org_id = uuid.uuid7()
            sandbox.clone(session.connection(), template, org_id, org_id.hex)
            box = DemoSandbox(
                org_id=org_id,
                template_org_id=template,
                salt=org_id.hex,
                created_at=now,
                expires_at=now + SANDBOX_TTL,
            )
            session.add(box)
            session.flush()
        user = session.scalars(
            select(User).where(
                User.id == sandbox.mapped(box.salt, uid("user", DEMO_PERSONAS[persona])),
                User.org_id == box.org_id,
                User.is_active,
            )
        ).first()
        if user is None:
            raise ApiError("not_found", "The demo organization is not loaded. Run python -m seed.v2.")
        sandbox_expires = box.expires_at
        caller = Caller(
            user_id=str(user.id),
            org_id=str(user.org_id),
            role=Role(user.role),
            outlet_id=str(user.outlet_id) if user.outlet_id else None,
            employee_id=str(user.employee_id) if user.employee_id else None,
        )
    token = issue(caller, not_after=sandbox_expires)
    exp = jwt.decode(token, settings().jwt_secret, algorithms=[ALGORITHM])["exp"]
    return s.DemoSession(
        access_token=token,
        expires_at=datetime.fromtimestamp(exp, UTC),
        me=me(caller),
        sandbox_id=uuid.UUID(caller.org_id),
        sandbox_expires_at=sandbox_expires,
    )
