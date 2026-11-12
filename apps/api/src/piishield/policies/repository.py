"""The only code that queries the database for policies."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from piishield.core.db import OrgScope, scoped
from piishield.policies.models import Policy


async def get_for_project(
    session: AsyncSession, scope: OrgScope, project_id: uuid.UUID
) -> Policy | None:
    stmt = scoped(select(Policy), Policy, scope).where(Policy.project_id == project_id)
    return await session.scalar(stmt)


def add(session: AsyncSession, policy: Policy) -> None:
    session.add(policy)
