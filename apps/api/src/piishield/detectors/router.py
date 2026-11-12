"""Plain scanning (no protection applied) and per-project custom recognizers."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from piishield.auth.dependencies import StaffRead, StaffWrite
from piishield.core.deps import SessionDep
from piishield.detectors import service
from piishield.detectors.models import CustomRecognizer
from piishield.detectors.schemas import (
    CustomRecognizerIn,
    CustomRecognizerOut,
    FindingOut,
    ScanResultOut,
    ScanTextIn,
)

router = APIRouter(prefix="/api/v1/detectors", tags=["detectors"])


@router.post(
    "/scan", response_model=ScanResultOut, summary="Scan text for findings (no protection applied)"
)
async def scan(body: ScanTextIn, actor: StaffRead, session: SessionDep) -> ScanResultOut:
    findings = await service.scan(session, actor.scope, body.project_id, body.text)
    return ScanResultOut(
        findings=[
            FindingOut(
                category=f.category,
                start=f.start,
                end=f.end,
                confidence=f.confidence,
                checksum_valid=f.checksum_valid,
                recognizer=f.recognizer,
            )
            for f in findings
        ],
        review_count=0,
    )


def _recognizer_out(r: CustomRecognizer) -> CustomRecognizerOut:
    return CustomRecognizerOut(
        id=r.id,
        project_id=r.project_id,
        name=r.name,
        category=r.category,
        pattern=r.pattern,
        confidence=r.confidence,
        enabled=r.enabled,
    )


@router.post(
    "/recognizers",
    response_model=CustomRecognizerOut,
    status_code=201,
    summary="Create a custom recognizer",
)
async def create_recognizer(
    body: CustomRecognizerIn, actor: StaffWrite, session: SessionDep
) -> CustomRecognizerOut:
    row = await service.create_custom_recognizer(
        session, actor, body.project_id, body.name, body.category, body.pattern, body.confidence
    )
    return _recognizer_out(row)


@router.get(
    "/recognizers",
    response_model=list[CustomRecognizerOut],
    summary="List a project's custom recognizers",
)
async def list_recognizers(
    project_id: uuid.UUID, actor: StaffRead, session: SessionDep
) -> list[CustomRecognizerOut]:
    rows = await service.list_custom_recognizers(session, actor.scope, project_id)
    return [_recognizer_out(r) for r in rows]


@router.delete(
    "/recognizers/{recognizer_id}", status_code=204, summary="Disable a custom recognizer"
)
async def delete_recognizer(
    recognizer_id: uuid.UUID, actor: StaffWrite, session: SessionDep
) -> None:
    await service.delete_custom_recognizer(session, actor, recognizer_id)
