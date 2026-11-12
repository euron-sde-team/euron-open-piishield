"""Project creation and management."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from piishield.audit.service import Actor, record
from piishield.core.db import OrgScope
from piishield.projects import repository
from piishield.projects.exceptions import DuplicateSlugError, ProjectNotFoundError
from piishield.projects.models import Project
from piishield.projects.schemas import ProjectIn, ProjectUpdate


async def list_projects(session: AsyncSession, scope: OrgScope) -> list[Project]:
    return await repository.list_projects(session, scope)


async def create_project(session: AsyncSession, actor: Actor, body: ProjectIn) -> Project:
    if await repository.slug_exists(session, actor.scope, body.slug):
        raise DuplicateSlugError(body.slug)
    project = Project(org_id=actor.org_id, **body.model_dump())
    repository.add(session, project)
    await session.flush()
    record(session, actor, "project.created", project_id=project.id, slug=body.slug)
    await session.commit()
    return project


async def get_project(session: AsyncSession, scope: OrgScope, project_id: uuid.UUID) -> Project:
    project = await repository.get_project(session, scope, project_id)
    if project is None:
        raise ProjectNotFoundError()
    return project


async def ensure_project(session: AsyncSession, scope: OrgScope, project_id: uuid.UUID) -> None:
    """AC12: every other domain accepts a caller-supplied ``project_id`` and must confirm
    it belongs to the caller's own org before writing or reading anything keyed to it.
    Without this, a request naming another org's project_id would silently create or
    query rows cross-tenant instead of 404ing, since most per-domain tables are scoped by
    (org_id, project_id) independently and a mismatched pair simply looks like "nothing
    yet" rather than "forbidden". Call this first, before any other work, in every public
    service function that takes a ``project_id`` from the request."""
    if await repository.get_project(session, scope, project_id) is None:
        raise ProjectNotFoundError()


async def update_project(
    session: AsyncSession, actor: Actor, project_id: uuid.UUID, body: ProjectUpdate
) -> Project:
    project = await get_project(session, actor.scope, project_id)
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(project, key, value)
    record(
        session,
        actor,
        "project.updated",
        project_id=project.id,
        **body.model_dump(exclude_none=True),
    )
    await session.commit()
    return project
