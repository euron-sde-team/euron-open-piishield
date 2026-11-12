"""Liveness, readiness and metrics."""

from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from piishield.core.deps import ContainerDep

router = APIRouter(tags=["health"])


@router.get("/healthz", summary="Liveness probe")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", summary="Readiness probe: database and cache reachable")
async def readyz(container: ContainerDep) -> dict[str, str]:
    async with container.db.sessionmaker() as session:
        await session.execute(text("SELECT 1"))
    await container.kv.ping()
    return {"status": "ready"}


@router.get("/metrics", summary="Prometheus metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
