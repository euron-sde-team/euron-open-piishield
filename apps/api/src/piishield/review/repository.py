"""The only code that queries the database for review items."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from piishield.core.db import OrgScope, get_scoped, scoped
from piishield.review.models import ReviewItem


async def list_pending(
    session: AsyncSession, scope: OrgScope, project_id: uuid.UUID | None = None
) -> list[ReviewItem]:
    stmt = scoped(select(ReviewItem), ReviewItem, scope).where(ReviewItem.status == "pending")
    if project_id is not None:
        stmt = stmt.where(ReviewItem.project_id == project_id)
    stmt = stmt.order_by(ReviewItem.created_at.desc())
    return list((await session.scalars(stmt)).all())


async def get(session: AsyncSession, scope: OrgScope, item_id: uuid.UUID) -> ReviewItem | None:
    return await get_scoped(session, ReviewItem, scope, item_id)


def add(session: AsyncSession, item: ReviewItem) -> None:
    session.add(item)
