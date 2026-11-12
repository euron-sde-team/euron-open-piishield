"""API application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from piishield import __version__
from piishield.ai_gateway.router import router as ai_gateway_router
from piishield.audit.router import router as audit_router
from piishield.auth.router import router as auth_router
from piishield.core.config import Settings, get_settings
from piishield.core.container import Container
from piishield.core.db import import_all_models
from piishield.core.errors import install_error_handlers
from piishield.core.logging import configure_logging
from piishield.core.middleware import BodySizeLimitMiddleware, RequestContextMiddleware
from piishield.database_scan.router import router as database_scan_router
from piishield.detectors.router import router as detectors_router
from piishield.documents.router import router as documents_router
from piishield.health.router import router as health_router
from piishield.policies.router import router as policies_router
from piishield.projects.router import router as projects_router
from piishield.protection.router import router as protection_router
from piishield.reports.router import router as reports_router
from piishield.review.router import router as review_router
from piishield.vault.router import router as vault_router

DESCRIPTION = """
Detects, masks, redacts, tokenizes and anonymizes personal and financial data across
text, JSON, documents and AI agent prompts/responses.

* **People** sign in with `POST /api/v1/auth/signup` or `/api/v1/auth/login` and use the
  session token as `Authorization: Bearer <token>`.
* **Automation / SDKs** use a project API key: `Authorization: Bearer pii_...`. A read key
  can scan and read; a write key can also mask, redact, tokenize and manage policies.
* **Vault access** (detokenizing a placeholder back to its original value) is a separate
  permission from any role or key scope: an owner must explicitly grant it with
  `POST /api/v1/vault/grants`.
* Every scan, mask, redact, tokenize and detokenize call is recorded in the audit log
  (`GET /api/v1/audit`), which never contains an original value or a vault mapping.
"""


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or get_settings()
    import_all_models()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.container = container or Container.build(settings)
        try:
            yield
        finally:
            if container is None:
                await app.state.container.close()

    app = FastAPI(
        title="Euron Open PIIShield",
        version=__version__,
        description=DESCRIPTION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
        separate_input_output_schemas=False,
    )
    install_error_handlers(app)
    for router in (
        health_router,
        auth_router,
        projects_router,
        policies_router,
        detectors_router,
        protection_router,
        vault_router,
        review_router,
        documents_router,
        database_scan_router,
        ai_gateway_router,
        reports_router,
        audit_router,
    ):
        app.include_router(router)

    app.add_middleware(GZipMiddleware, minimum_size=2048)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["authorization", "content-type", "x-request-id"],
        expose_headers=["x-request-id", "retry-after", "content-disposition"],
        max_age=600,
    )
    app.add_middleware(BodySizeLimitMiddleware, settings=settings)
    app.add_middleware(RequestContextMiddleware)
    return app
