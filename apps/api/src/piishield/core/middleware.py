"""Request-scoped context: request id, and a hard body-size cap."""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from piishield.core.logging import request_id_var


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["x-request-id"] = rid
        return response


class PayloadTooLargeError(Exception):
    def __init__(self, limit: int) -> None:
        super().__init__(f"Request body exceeds the {limit} byte limit")
        self.limit = limit


class BodySizeLimitMiddleware:
    """Refuse an oversized body before it is parsed (ASGI-level, checked via
    Content-Length so a multi-megabyte document upload is rejected cheaply)."""

    def __init__(self, app: ASGIApp, settings: object) -> None:
        self.app = app
        self.limit: int = getattr(settings, "max_body_bytes", 25_000_000)

    async def __call__(self, scope, receive, send):  # type: ignore[no-untyped-def]
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        length = headers.get(b"content-length")
        if length is not None and int(length) > self.limit:
            response = JSONResponse(
                {
                    "error": {
                        "code": "payload_too_large",
                        "type": "invalid_request_error",
                        "message": f"Request body exceeds the {self.limit} byte limit",
                        "details": {"limit_bytes": self.limit},
                    }
                },
                status_code=413,
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


__all__ = [
    "BodySizeLimitMiddleware",
    "PayloadTooLargeError",
    "RequestContextMiddleware",
    "Response",
]
