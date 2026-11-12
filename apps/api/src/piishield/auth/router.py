"""Signup, login and project API key management."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from piishield.auth import service
from piishield.auth.dependencies import StaffWrite
from piishield.auth.schemas import (
    ApiKeyCreated,
    ApiKeyIn,
    ApiKeyOut,
    LoginIn,
    SessionOut,
    SignupIn,
    UserOut,
)
from piishield.core.deps import ContainerDep, SessionDep
from piishield.core.security import issue_session
from piishield.orgs.models import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        org_id=user.org_id,
        email=user.email,
        name=user.name,
        role=user.role,
        vault_access=user.vault_access,
    )


@router.post(
    "/signup", response_model=SessionOut, status_code=201, summary="Create an organization"
)
async def signup(body: SignupIn, container: ContainerDep, session: SessionDep) -> SessionOut:
    _org, user = await service.signup(session, body.org_name, body.name, body.email, body.password)
    token = issue_session(
        user.id, user.role, user.session_version, container.settings.session_secret
    )
    return SessionOut(token=token, user=_user_out(user))


@router.post("/login", response_model=SessionOut, summary="Sign in")
async def login(body: LoginIn, container: ContainerDep, session: SessionDep) -> SessionOut:
    user = await service.authenticate(session, body.email, body.password)
    token = issue_session(
        user.id, user.role, user.session_version, container.settings.session_secret
    )
    return SessionOut(token=token, user=_user_out(user))


@router.post(
    "/keys", response_model=ApiKeyCreated, status_code=201, summary="Create a project API key"
)
async def create_key(
    body: ApiKeyIn, actor: StaffWrite, container: ContainerDep, session: SessionDep
) -> ApiKeyCreated:
    key, generated = await service.create_api_key(
        session, actor, body.project_id, body.name, body.scope, container.settings.api_key_pepper
    )
    return ApiKeyCreated(
        id=key.id, name=key.name, prefix=key.prefix, scope=key.scope, key=generated.plaintext
    )


@router.get("/keys", response_model=list[ApiKeyOut], summary="List a project's API keys")
async def list_keys(
    project_id: uuid.UUID, actor: StaffWrite, session: SessionDep
) -> list[ApiKeyOut]:
    rows = await service.list_api_keys(session, actor.scope, project_id)
    return [
        ApiKeyOut(
            id=r.id,
            project_id=r.project_id,
            name=r.name,
            prefix=r.prefix,
            scope=r.scope,
            revoked_at=r.revoked_at,
            last_used_at=r.last_used_at,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.delete("/keys/{key_id}", response_model=ApiKeyOut, summary="Revoke an API key")
async def revoke_key(key_id: uuid.UUID, actor: StaffWrite, session: SessionDep) -> ApiKeyOut:
    r = await service.revoke_api_key(session, actor, key_id)
    return ApiKeyOut(
        id=r.id,
        project_id=r.project_id,
        name=r.name,
        prefix=r.prefix,
        scope=r.scope,
        revoked_at=r.revoked_at,
        last_used_at=r.last_used_at,
        created_at=r.created_at,
    )
