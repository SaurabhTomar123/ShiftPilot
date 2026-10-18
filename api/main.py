"""HTTP API for the web demo, channels and admin panel.

    uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select

from agent.entrypoint import run_turn
from core.auth import Caller, PermissionDenied
from core.jsonable import jsonable
from core.tokens import issue, verify
from db.models import PendingAction
from db.session import tenant_session
from mcp_server.actions import decide
from mcp_server.context import caller_for_phone
from mcp_server.queries import as_uuid

app = FastAPI(title="ShiftPilot API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"],
                   allow_methods=["*"], allow_headers=["*"])

DEMO_PERSONAS = {
    "owner": "+919800000001",
    "cafe_manager": "+919800000002",
    "qsr_manager": "+919800000003",
    "kitchen_manager": "+919800000004",
}


def current_caller(authorization: Annotated[str, Header()] = "") -> Caller:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing bearer token")
    try:
        return verify(authorization.split(" ", 1)[1])
    except Exception as exc:
        raise HTTPException(401, "Invalid token") from exc


CallerDep = Annotated[Caller, Depends(current_caller)]


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


class DemoTokenIn(BaseModel):
    persona: str | None = None  # owner | cafe_manager | ... ; or pass a staff phone
    phone: str | None = None


@app.post("/auth/demo-token")
def demo_token(body: DemoTokenIn) -> dict[str, Any]:
    phone = body.phone or DEMO_PERSONAS.get(body.persona or "", "")
    if not phone:
        raise HTTPException(400, f"persona must be one of {list(DEMO_PERSONAS)} or pass phone")
    try:
        caller = caller_for_phone(phone)
    except PermissionDenied as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"token": issue(caller), "role": caller.role, "outlet_id": caller.outlet_id}


class ChatIn(BaseModel):
    message: str
    history: list[dict[str, Any]] = []


@app.post("/chat")
def chat(body: ChatIn, caller: CallerDep) -> dict[str, Any]:
    result = run_turn(caller, body.message, body.history, channel="web")
    return jsonable(result.__dict__)


@app.post("/chat/stream")
def chat_stream(body: ChatIn, caller: CallerDep) -> StreamingResponse:
    """SSE. TODO(M2): stream tokens + tool events from the graph (GRAPH.stream with
    stream_mode=["messages", "updates"]). For now emits the final result as one event."""
    def events() -> Iterator[str]:
        result = run_turn(caller, body.message, body.history, channel="web")
        for call in result.tool_calls:
            yield f"event: tool\ndata: {json.dumps(jsonable(call))}\n\n"
        yield f"event: final\ndata: {json.dumps(jsonable(result.__dict__))}\n\n"
    return StreamingResponse(events(), media_type="text/event-stream")


@app.get("/actions")
def list_actions(caller: CallerDep, status: str = "pending") -> list[dict[str, Any]]:
    with tenant_session(caller) as s:
        q = select(PendingAction).where(PendingAction.status == status)
        if caller.outlet_id:
            q = q.where(PendingAction.outlet_id == as_uuid(caller.outlet_id))
        rows = s.scalars(q.order_by(PendingAction.created_at.desc()).limit(100)).all()
        return [jsonable({"id": r.id, "tool": r.tool, "summary": r.summary_text,
                          "status": r.status, "requires": r.required_approver_role,
                          "expires_at": r.expires_at, "created_at": r.created_at})
                for r in rows]


@app.post("/actions/{action_id}/approve")
def approve(action_id: str, caller: CallerDep) -> dict[str, Any]:
    return _decide(caller, action_id, True)


@app.post("/actions/{action_id}/reject")
def reject(action_id: str, caller: CallerDep) -> dict[str, Any]:
    return _decide(caller, action_id, False)


def _decide(caller: Caller, action_id: str, approve_it: bool) -> dict[str, Any]:
    try:
        with tenant_session(caller) as s:
            return decide(s, caller, action_id, approve_it)
    except PermissionDenied as exc:
        raise HTTPException(403, str(exc)) from exc


@app.post("/sandbox/reset")
def sandbox_reset(caller: CallerDep) -> dict[str, Any]:
    if caller.role != "owner":
        raise HTTPException(403, "Only the owner persona can reset the sandbox")
    from seed.load import load
    return {"reset": load()}


# TODO(M5): POST /webhooks/whatsapp (verify X-Hub-Signature-256), POST /voice/session
# TODO(M6): POST /import/csv, POST /import/{id}/commit
# TODO(M3): GET /evals/runs, GET /evals/runs/{id} (serve evals/reports/*.json)
