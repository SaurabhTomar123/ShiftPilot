"""The scheduling v2 API as its own FastAPI app (the v1 chat API in api.main stays frozen).

python -m uvicorn api.v2.app:app --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.v2.routes import install
from api.v2.schemas import CONTRACT_VERSION
from core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title="ShiftPilot scheduling v2 API", version=CONTRACT_VERSION)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings().cors_origins.split(",") if o.strip()],
        allow_methods=["GET", "POST", "PUT", "PATCH"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "If-None-Match"],
        expose_headers=["ETag", "Retry-After"],
    )
    install(app)

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        return {"status": "ok", "contract_version": CONTRACT_VERSION}

    return app


app = create_app()
