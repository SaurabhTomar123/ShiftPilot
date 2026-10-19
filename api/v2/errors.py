"""One error envelope for every v2 failure: {"error": {code, message, retryable, details, trace_id}}."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.v2 import schemas as s
from core.auth import PermissionDenied

STATUS: dict[str, int] = {
    "unauthenticated": 401,
    "permission_denied": 403,
    "not_found": 404,
    "validation_failed": 422,
    "stale_version": 409,
    "conflict": 409,
    "idempotency_conflict": 409,
    "run_in_progress": 409,
    "rate_limited": 429,
    "not_implemented": 501,
    "internal": 500,
}


class ApiError(Exception):
    def __init__(self, code: s.ErrorCode, message: str, *, retryable: bool = False, **details: Any) -> None:
        super().__init__(message)
        self.code, self.message, self.retryable, self.details = code, message, retryable, details

    @property
    def status(self) -> int:
        return STATUS[self.code]

    def body(self) -> dict[str, Any]:
        err = s.ErrorBody(
            code=self.code, message=self.message, retryable=self.retryable, details=self.details
        )
        return s.ErrorResponse(error=err).model_dump(mode="json")


def response(err: ApiError, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(status_code=err.status, content=err.body(), headers=headers)


def not_found(what: str) -> ApiError:
    return ApiError("not_found", f"{what} not found.")


def install(app: FastAPI) -> None:
    async def on_api_error(_request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, ApiError)
        return response(exc)

    async def on_permission(_request: Request, exc: Exception) -> JSONResponse:
        return response(ApiError("permission_denied", str(exc) or "You do not have access to this."))

    async def on_validation(_request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, RequestValidationError)
        fields = [
            {
                "path": [p for p in e.get("loc", ()) if p not in ("body", "query", "path", "header")],
                "message": str(e.get("msg", "Invalid value.")),
            }
            for e in exc.errors()
        ]
        return response(ApiError("validation_failed", "Some fields need attention.", fields=fields))

    app.add_exception_handler(ApiError, on_api_error)
    app.add_exception_handler(PermissionDenied, on_permission)
    app.add_exception_handler(RequestValidationError, on_validation)
