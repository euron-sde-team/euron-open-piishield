"""Per-project policy CRUD."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from piishield.auth.dependencies import StaffRead, StaffWrite
from piishield.core.deps import ContainerDep, SessionDep
from piishield.policies import service
from piishield.policies.models import Policy
from piishield.policies.schemas import PolicyIn, PolicyOut

router = APIRouter(prefix="/api/v1/projects/{project_id}/policy", tags=["policies"])


def _out(p: Policy) -> PolicyOut:
    return PolicyOut(
        id=p.id,
        project_id=p.project_id,
        required_categories=p.required_categories,
        masking_method=p.masking_method,
        partial_mask_reveal=p.partial_mask_reveal,
        confidence_threshold=p.confidence_threshold,
        retention_days=p.retention_days,
    )


@router.get("", response_model=PolicyOut, summary="Get a project's policy")
async def get_policy(project_id: uuid.UUID, actor: StaffRead, session: SessionDep) -> PolicyOut:
    return _out(await service.get_or_404(session, actor.scope, project_id))


@router.put("", response_model=PolicyOut, summary="Replace a project's policy")
async def put_policy(
    project_id: uuid.UUID,
    body: PolicyIn,
    actor: StaffWrite,
    container: ContainerDep,
    session: SessionDep,
) -> PolicyOut:
    return _out(await service.upsert(session, container.kv, actor, project_id, body))
