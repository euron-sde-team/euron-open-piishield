"""Who is calling.

* **People** use the dashboard with a session (``Authorization: Bearer <session token>``).
  Roles rank ``viewer < admin < owner``.
* **Automation / the SDKs** use a project API key (``pii_<prefix>_<secret>``) with scope
  ``read`` or ``write``. A read key reads like a viewer; a write key acts like an admin.
* **Vault access** (AC5) is a permission separate from role or key scope: checked by
  ``VaultAccess`` below, never implied by ``owner``/``admin``/a write key alone.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from piishield.audit.service import Actor
from piishield.core.deps import ContainerDep, SessionDep
from piishield.core.errors import AuthenticationError, PermissionDeniedError
from piishield.core.security import (
    API_KEY_PREFIX,
    constant_time_equals,
    decode_session,
    hash_key_secret,
    parse_api_key,
)
from piishield.orgs.models import User

ROLE_RANK = {"viewer": 0, "admin": 1, "owner": 2}
SEEN_EVERY = timedelta(minutes=1)


def bearer(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    token = header[7:].strip() if header.lower().startswith("bearer ") else None
    return token or None


async def current_user(request: Request, container: ContainerDep, session: SessionDep) -> User:
    token = bearer(request)
    if not token or token.startswith(f"{API_KEY_PREFIX}_"):
        raise AuthenticationError("Sign in to continue", code="not_signed_in")
    claims = decode_session(token, container.settings.session_secret)
    if claims is None:
        raise AuthenticationError("Your session expired. Sign in again", code="session_expired")
    user = await session.get(User, claims.user_id)
    if user is None or user.disabled or user.session_version != claims.session_version:
        raise AuthenticationError("Your session expired. Sign in again", code="session_expired")
    now = datetime.now(UTC)
    if user.last_seen_at is None or now - user.last_seen_at > SEEN_EVERY:
        user.last_seen_at = now
        await session.commit()
    request.state.actor = Actor(user.org_id, user.id, user.email, user.role, kind="user")
    request.state.vault_access = user.vault_access
    request.state.user = user
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def has_role(role: str, required: str) -> bool:
    return ROLE_RANK.get(role, -1) >= ROLE_RANK.get(required, 99)


async def _api_key_actor(session: AsyncSession, pepper: str, raw: str) -> tuple[Actor, bool, str]:
    """Returns (actor, has_vault_access, scope)."""
    from piishield.auth.models import ApiKey
    from piishield.vault.models import VaultGrant

    parsed = parse_api_key(raw)
    if parsed is None:
        raise AuthenticationError("The API key is malformed", code="invalid_api_key")
    prefix, secret = parsed
    key = await session.scalar(select(ApiKey).where(ApiKey.prefix == prefix))
    expected = hash_key_secret(secret, pepper)
    if (
        key is None
        or key.revoked_at is not None
        or not constant_time_equals(key.secret_hash, expected)
    ):
        raise AuthenticationError("The API key is invalid or revoked", code="invalid_api_key")
    now = datetime.now(UTC)
    if key.last_used_at is None or now - key.last_used_at > SEEN_EVERY:
        key.last_used_at = now
        await session.commit()
    role = "admin" if key.scope == "write" else "viewer"
    actor = Actor(key.org_id, key.id, f"api-key:{key.name}", role, kind="api_key")
    grant = await session.scalar(
        select(VaultGrant).where(VaultGrant.api_key_id == key.id, VaultGrant.revoked_at.is_(None))
    )
    return actor, grant is not None, key.scope


async def _resolve_actor(
    request: Request, container: ContainerDep, session: SessionDep
) -> tuple[Actor, bool]:
    """The calling actor and whether they hold vault access, from either a session or an
    API key. Cached on request.state so repeated dependencies in one request do not
    re-authenticate twice."""
    if hasattr(request.state, "actor"):
        return request.state.actor, bool(getattr(request.state, "vault_access", False))
    token = bearer(request)
    if token and token.startswith(f"{API_KEY_PREFIX}_"):
        actor, vault_access, _scope = await _api_key_actor(
            session, container.settings.api_key_pepper, token
        )
        request.state.actor = actor
        request.state.vault_access = vault_access
        return actor, vault_access
    user = await current_user(request, container, session)
    actor = Actor(user.org_id, user.id, user.email, user.role, kind="user")
    return actor, user.vault_access


def staff(role: str) -> Callable[..., Coroutine[Any, Any, Actor]]:
    """A signed-in person with at least ``role``, or a management API key whose scope
    covers it (read covers viewer; write covers admin)."""

    async def dependency(request: Request, container: ContainerDep, session: SessionDep) -> Actor:
        actor, _ = await _resolve_actor(request, container, session)
        if not has_role(actor.role, role):
            raise PermissionDeniedError(
                f"This needs the {role} role (or a key with that scope)", code="insufficient_role"
            )
        return actor

    return dependency


async def vault_access(request: Request, container: ContainerDep, session: SessionDep) -> Actor:
    """AC5: detokenization requires its own permission, never implied by owner/admin or a
    write-scoped key alone."""
    actor, has_access = await _resolve_actor(request, container, session)
    if not has_access:
        raise PermissionDeniedError(
            "This action needs vault access, which is granted separately from your role",
            code="vault_access_required",
        )
    return actor


StaffRead = Annotated[Actor, Depends(staff("viewer"))]
StaffWrite = Annotated[Actor, Depends(staff("admin"))]
OrgOwner = Annotated[Actor, Depends(staff("owner"))]
VaultAccess = Annotated[Actor, Depends(vault_access)]
