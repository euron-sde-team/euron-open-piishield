"""The only code that queries the database for projects."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from piishield.core.db import OrgScope, get_scoped, scoped
from piishield.projects.models import Project


async def list_projects(session: AsyncSession, scope: OrgScope) -> list[Project]:
    stmt = scoped(select(Project), Project, scope).order_by(Project.name)
    return list((await session.scalars(stmt)).all())


async def get_project(
    session: AsyncSession, scope: OrgScope, project_id: uuid.UUID
) -> Project | None:
    return await get_scoped(session, Project, scope, project_id)


async def slug_exists(session: AsyncSession, scope: OrgScope, slug: str) -> bool:
    stmt = scoped(select(Project.id), Project, scope).where(Project.slug == slug)
    return await session.scalar(stmt) is not None


def add(session: AsyncSession, project: Project) -> None:
    session.add(project)
