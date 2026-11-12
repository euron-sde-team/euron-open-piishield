"""The only code that queries the database for vault entries and grants."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from piishield.core.db import OrgScope, scoped
from piishield.vault.models import VaultEntry, VaultGrant


async def find_by_fingerprint(
    session: AsyncSession, scope: OrgScope, project_id: uuid.UUID, scope_id: str, fingerprint: str
) -> VaultEntry | None:
    stmt = scoped(select(VaultEntry), VaultEntry, scope).where(
        VaultEntry.project_id == project_id,
        VaultEntry.scope_id == scope_id,
        VaultEntry.value_fingerprint == fingerprint,
    )
    return await session.scalar(stmt)


async def find_by_placeholder(
    session: AsyncSession, scope: OrgScope, project_id: uuid.UUID, scope_id: str, placeholder: str
) -> VaultEntry | None:
    stmt = scoped(select(VaultEntry), VaultEntry, scope).where(
        VaultEntry.project_id == project_id,
        VaultEntry.scope_id == scope_id,
        VaultEntry.placeholder == placeholder,
    )
    return await session.scalar(stmt)


async def count_placeholders_in_scope(
    session: AsyncSession, scope: OrgScope, project_id: uuid.UUID, scope_id: str, category: str
) -> int:
    from sqlalchemy import func

    stmt = scoped(select(func.count()), VaultEntry, scope).where(
        VaultEntry.project_id == project_id,
        VaultEntry.scope_id == scope_id,
        VaultEntry.category == category,
    )
    return int((await session.scalar(stmt)) or 0)


def add(session: AsyncSession, entry: VaultEntry) -> None:
    session.add(entry)


async def active_grant(
    session: AsyncSession,
    scope: OrgScope,
    *,
    user_id: uuid.UUID | None,
    api_key_id: uuid.UUID | None,
) -> VaultGrant | None:
    stmt = scoped(select(VaultGrant), VaultGrant, scope).where(VaultGrant.revoked_at.is_(None))
    if user_id is not None:
        stmt = stmt.where(VaultGrant.user_id == user_id)
    elif api_key_id is not None:
        stmt = stmt.where(VaultGrant.api_key_id == api_key_id)
    else:
        return None
    return await session.scalar(stmt)


async def list_grants(session: AsyncSession, scope: OrgScope) -> list[VaultGrant]:
    stmt = scoped(select(VaultGrant), VaultGrant, scope).where(VaultGrant.revoked_at.is_(None))
    return list((await session.scalars(stmt)).all())


def add_grant(session: AsyncSession, grant: VaultGrant) -> None:
    session.add(grant)
