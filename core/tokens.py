"""JWTs carry the caller identity from the API/web demo into the agent and the MCP server."""

from datetime import UTC, datetime, timedelta

import jwt

from core.auth import Caller, Role
from core.config import settings

ALGORITHM = "HS256"


def issue(caller: Caller) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": caller.user_id,
        "org": caller.org_id,
        "role": caller.role.value,
        "outlet": caller.outlet_id,
        "emp": caller.employee_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings().jwt_ttl_minutes),
    }
    return jwt.encode(claims, settings().jwt_secret, algorithm=ALGORITHM)


def verify(token: str) -> Caller:
    claims = jwt.decode(token, settings().jwt_secret, algorithms=[ALGORITHM])
    return Caller(
        user_id=claims["sub"],
        org_id=claims["org"],
        role=Role(claims["role"]),
        outlet_id=claims.get("outlet"),
        employee_id=claims.get("emp"),
    )
