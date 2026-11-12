"""Typed application errors and the single place they become HTTP responses.

The body shape is ``{"error": {"code", "type", "message", "details"}}`` for every error,
consistent for the dashboard and both SDKs.

Unlike a security enforcement gate, PIIShield is a detection and privacy tool: a dependency
being down degrades a request (returns a clear 503 so the caller can retry) rather than
silently pretending nothing was found. It never fails open by skipping detection or the
vault's encryption step without saying so (see ``vault.service`` and ``protection.service``
for where that is enforced at the call site).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from redis.exceptions import RedisError
from sqlalchemy.exc import IntegrityError, InterfaceError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("piishield.errors")


class AppError(Exception):
    status_code = 400
    code = "bad_request"
    type = "invalid_request_error"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.details = details or {}
        self.headers = headers or {}

    def body(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "type": self.type,
                "message": self.message,
                "details": self.details,
            }
        }


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class AuthenticationError(AppError):
    status_code = 401
    code = "unauthenticated"
    type = "authentication_error"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "forbidden"
    type = "permission_error"


class PolicyRefusedError(AppError):
    """AC10: a required category requested with masking disabled. The raw value is never
    passed through; the caller must either enable masking or accept the policy default."""

    status_code = 422
    code = "policy_refused"
    type = "policy_error"


class DependencyUnavailableError(AppError):
    """Postgres, Redis or the mock AI backend is unreachable. The caller gets a clear,
    retryable error; no finding or protection output is silently fabricated or skipped."""

    status_code = 503
    code = "dependency_unavailable"
    type = "service_unavailable"


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(exc.body(), status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"loc": list(e.get("loc", [])), "msg": e.get("msg", ""), "type": e.get("type", "")}
            for e in exc.errors()
        ]
        err = AppError("Request validation failed", code="validation_error")
        err.details = {"errors": errors}
        return JSONResponse(err.body(), status_code=422)

    @app.exception_handler(ValidationError)
    async def _model_validation(_: Request, exc: ValidationError) -> JSONResponse:
        errors = [
            {"loc": list(e.get("loc", [])), "msg": e.get("msg", ""), "type": e.get("type", "")}
            for e in exc.errors(include_url=False, include_input=False)
        ]
        err = AppError("Request validation failed", code="validation_error")
        err.details = {"errors": errors}
        return JSONResponse(err.body(), status_code=422)

    @app.exception_handler(IntegrityError)
    async def _integrity(request: Request, exc: IntegrityError) -> JSONResponse:
        log.warning(
            "integrity conflict",
            extra={"path": request.url.path, "constraint": _constraint(exc)},
        )
        err = ConflictError(
            "This conflicts with a change made at the same time. Reload and try again",
            code="conflict",
        )
        return JSONResponse(err.body(), status_code=409)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        err = AppError(str(exc.detail), code="http_error")
        return JSONResponse(err.body(), status_code=exc.status_code)

    async def _unavailable(request: Request, exc: Exception) -> JSONResponse:
        # A dependency (Postgres, Redis, the mock AI service) is down. PIIShield degrades
        # predictably: a clear 503 asking the caller to retry, never a response that
        # silently omits findings or skips the vault's encryption step.
        log.warning(
            "dependency unavailable", extra={"path": request.url.path, "error": type(exc).__name__}
        )
        err = DependencyUnavailableError(
            "PIIShield could not reach a dependency; nothing was scanned, masked or stored. Retry shortly"
        )
        return JSONResponse(err.body(), status_code=503, headers={"retry-after": "5"})

    for unavailable in (
        OperationalError,
        InterfaceError,
        PoolTimeoutError,
        RedisError,
        ConnectionError,
        TimeoutError,
        OSError,
    ):
        app.add_exception_handler(unavailable, _unavailable)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error", extra={"path": request.url.path})
        err = AppError("Internal server error", code="internal_error")
        err.type = "api_error"
        return JSONResponse(err.body(), status_code=500)


def _constraint(exc: IntegrityError) -> str | None:
    diag = getattr(getattr(exc.orig, "__cause__", None), "constraint_name", None)
    return diag or getattr(exc.orig, "constraint_name", None)
