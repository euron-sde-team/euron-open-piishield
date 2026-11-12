"""The only code that queries the database for AI gateway call records."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from piishield.ai_gateway.models import GatewayCall


def record_call(
    session: AsyncSession,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    scope_id: str,
    stage: str,
    finding_count: int,
    categories: list[str],
) -> GatewayCall:
    call = GatewayCall(
        org_id=org_id,
        project_id=project_id,
        scope_id=scope_id,
        stage=stage,
        finding_count=finding_count,
        categories=sorted(set(categories)),
    )
    session.add(call)
    return call
