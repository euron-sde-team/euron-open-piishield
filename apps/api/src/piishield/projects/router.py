"""Project CRUD."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from piishield.auth.dependencies import StaffRead, StaffWrite
from piishield.core.deps import SessionDep
from piishield.projects import service
from piishield.projects.models import Project
from piishield.projects.schemas import ProjectIn, ProjectOut, ProjectUpdate

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def _out(p: Project) -> ProjectOut:
    return ProjectOut(
        id=p.id, name=p.name, slug=p.slug, description=p.description, created_at=p.created_at
    )


@router.get("", response_model=list[ProjectOut], summary="List projects")
async def list_projects(actor: StaffRead, session: SessionDep) -> list[ProjectOut]:
    rows = await service.list_projects(session, actor.scope)
    return [_out(r) for r in rows]


@router.post("", response_model=ProjectOut, status_code=201, summary="Create a project")
async def create_project(body: ProjectIn, actor: StaffWrite, session: SessionDep) -> ProjectOut:
    return _out(await service.create_project(session, actor, body))


@router.get("/{project_id}", response_model=ProjectOut, summary="Get a project")
async def get_project(project_id: uuid.UUID, actor: StaffRead, session: SessionDep) -> ProjectOut:
    return _out(await service.get_project(session, actor.scope, project_id))


@router.patch("/{project_id}", response_model=ProjectOut, summary="Update a project")
async def update_project(
    project_id: uuid.UUID, body: ProjectUpdate, actor: StaffWrite, session: SessionDep
) -> ProjectOut:
    return _out(await service.update_project(session, actor, project_id, body))
