"""Scan and protect: text and JSON."""

from __future__ import annotations

from fastapi import APIRouter

from piishield.auth.dependencies import StaffWrite
from piishield.core.deps import ContainerDep, SessionDep
from piishield.protection import service
from piishield.protection.schemas import (
    ProtectedFindingOut,
    ProtectJsonIn,
    ProtectJsonOut,
    ProtectTextIn,
    ProtectTextOut,
)
from piishield.protection.service import ProtectedFinding

router = APIRouter(prefix="/api/v1/protect", tags=["protection"])


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


@router.post("/text", response_model=ProtectTextOut, summary="Scan and protect free text")
async def protect_text(
    body: ProtectTextIn, actor: StaffWrite, container: ContainerDep, session: SessionDep
) -> ProtectTextOut:
    protected, findings, scope_id = await service.protect_text(
        session,
        container.kv,
        container.sealer,
        actor,
        body.project_id,
        body.text,
        method_overrides=dict(body.method_overrides),
        skip_categories=body.skip_categories,
        scope_id=body.scope_id,
    )
    review_count = sum(1 for f in findings if f.in_review)
    return ProtectTextOut(
        protected=protected,
        findings=[_finding_out(f) for f in findings],
        review_count=review_count,
        scope_id=scope_id,
    )


@router.post("/json", response_model=ProtectJsonOut, summary="Scan and protect a JSON payload")
async def protect_json(
    body: ProtectJsonIn, actor: StaffWrite, container: ContainerDep, session: SessionDep
) -> ProtectJsonOut:
    protected, findings, scope_id = await service.protect_json(
        session,
        container.kv,
        container.sealer,
        actor,
        body.project_id,
        body.payload,
        method_overrides=dict(body.method_overrides),
        skip_categories=body.skip_categories,
        scope_id=body.scope_id,
    )
    review_count = sum(1 for f in findings if f.in_review)
    return ProtectJsonOut(
        protected=protected,
        findings=[_finding_out(f) for f in findings],
        review_count=review_count,
        scope_id=scope_id,
    )
