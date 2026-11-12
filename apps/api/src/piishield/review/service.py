"""The review queue: low-confidence findings land here (AC13); an authorized person lists,
approves (treats as protected) or dismisses (treats as a false positive) each one."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from piishield.audit.service import Actor, record
from piishield.core.db import OrgScope
from piishield.detectors.recognizers import Finding
from piishield.review import repository
from piishield.review.exceptions import ReviewItemAlreadyDecidedError, ReviewItemNotFoundError
from piishield.review.models import ReviewItem


def queue_finding(
    session: AsyncSession,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    finding: Finding,
    *,
    already_protected: bool,
) -> ReviewItem:
    item = ReviewItem(
        org_id=org_id,
        project_id=project_id,
        category=finding.category,
        start=finding.start,
        end=finding.end,
        confidence=finding.confidence,
        recognizer=finding.recognizer,
        already_protected=already_protected,
    )
    repository.add(session, item)
    return item


async def list_pending(
    session: AsyncSession, scope: OrgScope, project_id: uuid.UUID | None = None
) -> list[ReviewItem]:
    return await repository.list_pending(session, scope, project_id)


async def _decide(
    session: AsyncSession, actor: Actor, item_id: uuid.UUID, status: str
) -> ReviewItem:
    item = await repository.get(session, actor.scope, item_id)
    if item is None:
        raise ReviewItemNotFoundError()
    if item.status != "pending":
        raise ReviewItemAlreadyDecidedError()
    item.status = status
    item.decided_at = datetime.now(UTC)
    item.decided_by = actor.id
    record(
        session,
        actor,
        f"review.{status}",
        project_id=item.project_id,
        finding_count=1,
        categories=[item.category],
    )
    await session.commit()
    return item


async def approve(session: AsyncSession, actor: Actor, item_id: uuid.UUID) -> ReviewItem:
    """Approve: the finding is treated as protected going forward (a human confirmed it
    is real PII). 0.1.0 does not retroactively re-protect already-returned content; it
    records the decision so future scans of the same recognizer/category combination can
    be tuned, and so the demo/dashboard shows a resolved item."""
    return await _decide(session, actor, item_id, "approved")


async def dismiss(session: AsyncSession, actor: Actor, item_id: uuid.UUID) -> ReviewItem:
    """Dismiss: a human confirmed this is a false positive."""
    return await _decide(session, actor, item_id, "dismissed")
