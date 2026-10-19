"""v2 identity: bearer JWT -> Caller, capabilities per role, and synthetic demo sessions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from api.v2 import schemas as s
from api.v2.errors import ApiError
from core.auth import Caller, Role
from core.config import settings
from core.tokens import ALGORITHM, issue, verify
from db.models import Organization, User
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


def demo_session(persona: str) -> s.DemoSession:
    """Synthetic demo only. The user is looked up by its deterministic seed ID inside the demo org,
    so this can never issue a token for another tenant's user."""
    if not settings().demo_sessions_enabled:
        raise ApiError("permission_denied", "Demo sessions are not available on this deployment.")
    demo_org = uid("org", settings().demo_org_key)
    with admin_session() as session:
        user = session.scalars(
            select(User).where(
                User.id == uid("user", DEMO_PERSONAS[persona]), User.org_id == demo_org, User.is_active
            )
        ).first()
        if user is None:
            raise ApiError("not_found", "The demo organization is not loaded. Run python -m seed.v2.")
        caller = Caller(
            user_id=str(user.id),
            org_id=str(user.org_id),
            role=Role(user.role),
            outlet_id=str(user.outlet_id) if user.outlet_id else None,
            employee_id=str(user.employee_id) if user.employee_id else None,
        )
    token = issue(caller)
    exp = jwt.decode(token, settings().jwt_secret, algorithms=[ALGORITHM])["exp"]
    return s.DemoSession(access_token=token, expires_at=datetime.fromtimestamp(exp, UTC), me=me(caller))
