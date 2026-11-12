"""The only code that queries the database for custom recognizers."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from piishield.core.db import OrgScope, get_scoped, scoped
from piishield.detectors.models import CustomRecognizer


async def list_for_project(
    session: AsyncSession, scope: OrgScope, project_id: uuid.UUID
) -> list[CustomRecognizer]:
    stmt = scoped(select(CustomRecognizer), CustomRecognizer, scope).where(
        CustomRecognizer.project_id == project_id, CustomRecognizer.enabled.is_(True)
    )
    return list((await session.scalars(stmt)).all())


async def get(
    session: AsyncSession, scope: OrgScope, recognizer_id: uuid.UUID
) -> CustomRecognizer | None:
    return await get_scoped(session, CustomRecognizer, scope, recognizer_id)


def add(session: AsyncSession, recognizer: CustomRecognizer) -> None:
    session.add(recognizer)
