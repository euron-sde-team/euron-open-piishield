"""The AI privacy gateway: protect before the call, restore after it."""

from __future__ import annotations

from fastapi import APIRouter

from piishield.ai_gateway import service
from piishield.ai_gateway.schemas import (
    GatewayProtectIn,
    GatewayProtectOut,
    GatewayRestoreIn,
    GatewayRestoreOut,
)
from piishield.auth.dependencies import StaffWrite
from piishield.core.deps import ContainerDep, SessionDep
from piishield.protection.schemas import ProtectedFindingOut
from piishield.protection.service import ProtectedFinding

router = APIRouter(prefix="/api/v1/ai-gateway", tags=["ai_gateway"])


def _finding_out(f: ProtectedFinding) -> ProtectedFindingOut:
    return ProtectedFindingOut(
        category=f.category,
        start=f.start,
        end=f.end,
        confidence=f.confidence,
        checksum_valid=f.checksum_valid,
        recognizer=f.recognizer,
        method=f.method,
        placeholder=f.placeholder,
        in_review=f.in_review,
    )


@router.post(
    "/protect",
    response_model=GatewayProtectOut,
    summary="Protect a prompt before sending it to a model",
)
async def protect(
    body: GatewayProtectIn, actor: StaffWrite, container: ContainerDep, session: SessionDep
) -> GatewayProtectOut:
    protected, findings, scope_id = await service.protect(
        session, container.kv, container.sealer, actor, body.project_id, body.prompt, body.scope_id
    )
    return GatewayProtectOut(
        protected_prompt=protected, findings=[_finding_out(f) for f in findings], scope_id=scope_id
    )


@router.post(
    "/restore",
    response_model=GatewayRestoreOut,
    summary="Restore placeholders in a model's response",
)
async def restore(
    body: GatewayRestoreIn, actor: StaffWrite, container: ContainerDep, session: SessionDep
) -> GatewayRestoreOut:
    restored, count = await service.restore(
        session,
        container.sealer,
        actor.scope,
        actor,
        body.project_id,
        body.scope_id,
        body.model_response,
    )
    return GatewayRestoreOut(restored_response=restored, placeholders_restored=count)
