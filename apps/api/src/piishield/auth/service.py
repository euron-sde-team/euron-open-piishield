"""Signup, login, and project API key issuance/revocation."""

from __future__ import annotations

import re
import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from piishield.audit.service import Actor, record
from piishield.auth.models import ApiKey
from piishield.core.db import OrgScope, get_scoped
from piishield.core.errors import AuthenticationError, ConflictError, NotFoundError
from piishield.core.security import (
    GeneratedKey,
    generate_api_key,
    hash_password,
    password_problems,
    verify_password,
)
from piishield.orgs.models import Organization, User


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40]
    return slug or "org"


async def unique_slug(session: AsyncSession, name: str) -> str:
    base = slugify(name)
    slug = base
    while (
        await session.scalar(select(Organization.id).where(Organization.slug == slug)) is not None
    ):
        slug = f"{base}-{secrets.token_hex(2)}"
    return slug


async def signup(
    session: AsyncSession, org_name: str, name: str, email: str, password: str
) -> tuple[Organization, User]:
    """A new organization with its first user as owner, including vault access (the first
    owner must be able to reach everything they just created)."""
    if problems := password_problems(password):
        raise AuthenticationError(
            "Weak password: needs " + ", ".join(problems), code="weak_password"
        )
    existing = await session.scalar(select(User.id).where(User.email == email.lower()))
    if existing is not None:
        raise ConflictError("An account with this email already exists", code="duplicate_email")
    org = Organization(name=org_name, slug=await unique_slug(session, org_name))
    session.add(org)
    await session.flush()
    user = User(
        org_id=org.id,
        email=email.lower(),
        name=name,
        password_hash=hash_password(password),
        role="owner",
        vault_access=True,
    )
    session.add(user)
    await session.flush()
    record(session, Actor(org.id, user.id, user.email, user.role), "org.created", org_name=org_name)
    await session.commit()
    return org, user


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    user = await session.scalar(select(User).where(User.email == email.lower()))
    if user is None or user.disabled or not verify_password(password, user.password_hash):
        raise AuthenticationError("Incorrect email or password", code="invalid_credentials")
    return user


async def create_api_key(
    session: AsyncSession, actor: Actor, project_id: uuid.UUID, name: str, scope: str, pepper: str
) -> tuple[ApiKey, GeneratedKey]:
    from piishield.projects.models import Project

    project = await get_scoped(session, Project, actor.scope, project_id)
    if project is None:
        raise NotFoundError("Project not found")
    generated = generate_api_key(pepper)
    key = ApiKey(
        org_id=actor.org_id,
        project_id=project_id,
        name=name,
        prefix=generated.prefix,
        secret_hash=generated.secret_hash,
        scope=scope,
        created_by=actor.id,
    )
    session.add(key)
    await session.flush()
    record(session, actor, "key.created", project_id=project_id, name=name, scope=scope)
    await session.commit()
    return key, generated


async def list_api_keys(
    session: AsyncSession, scope: OrgScope, project_id: uuid.UUID
) -> list[ApiKey]:
    return list(
        (
            await session.scalars(
                select(ApiKey)
                .where(ApiKey.org_id == scope.org_id, ApiKey.project_id == project_id)
                .order_by(ApiKey.created_at.desc())
            )
        ).all()
    )


async def revoke_api_key(session: AsyncSession, actor: Actor, key_id: uuid.UUID) -> ApiKey:
    from datetime import UTC, datetime

    key = await get_scoped(session, ApiKey, actor.scope, key_id)
    if key is None:
        raise NotFoundError("API key not found")
    key.revoked_at = datetime.now(UTC)
    record(session, actor, "key.revoked", project_id=key.project_id, name=key.name)
    await session.commit()
    return key
