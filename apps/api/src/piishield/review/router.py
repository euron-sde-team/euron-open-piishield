"""The review queue: list, approve, dismiss."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from piishield.auth.dependencies import StaffRead, StaffWrite
from piishield.core.deps import SessionDep
from piishield.review import service
from piishield.review.models import ReviewItem
from piishield.review.schemas import ReviewItemOut

router = APIRouter(prefix="/api/v1/review", tags=["review"])


def _out(i: ReviewItem) -> ReviewItemOut:
    return ReviewItemOut(
        id=i.id,
        project_id=i.project_id,
        category=i.category,
        start=i.start,
        end=i.end,
        confidence=i.confidence,
        recognizer=i.recognizer,
        already_protected=i.already_protected,
        status=i.status,
        created_at=i.created_at,
        decided_at=i.decided_at,
    )


@router.get("", response_model=list[ReviewItemOut], summary="List pending review items")
async def list_pending(
    actor: StaffRead, session: SessionDep, project_id: uuid.UUID | None = None
) -> list[ReviewItemOut]:
    rows = await service.list_pending(session, actor.scope, project_id)
    return [_out(r) for r in rows]


@router.post("/{item_id}/approve", response_model=ReviewItemOut, summary="Approve a finding")
async def approve(item_id: uuid.UUID, actor: StaffWrite, session: SessionDep) -> ReviewItemOut:
    return _out(await service.approve(session, actor, item_id))


@router.post("/{item_id}/dismiss", response_model=ReviewItemOut, summary="Dismiss a finding")
async def dismiss(item_id: uuid.UUID, actor: StaffWrite, session: SessionDep) -> ReviewItemOut:
    return _out(await service.dismiss(session, actor, item_id))
