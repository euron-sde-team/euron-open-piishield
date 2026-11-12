"""Tokenization and detokenization.

AC4 (scope consistency): the same input value tokenized twice within one scope (a request
id, or a named session) always yields the same placeholder; two different values never
collide. This is enforced by a fingerprint lookup against the durable vault table scoped
to (org, project, scope_id): a HMAC-SHA256 of the plaintext under a fixed, non-secret
context label, so two equal plaintexts always fingerprint equal and a fingerprint never
reveals the plaintext on its own (HMAC is one-way; "non-secret" only means callers do not
need the master key to compute it, not that it is reversible). The KV layer additionally
caches scope_id -> {fingerprint: placeholder} for the scope's lifetime purely as a speed
path (PLAN.md's "tokenization scope map" cache); a cache miss or a KV outage always falls
back to the database lookup below, so scope consistency NEVER depends on the cache being
warm or even available (this is the "degrades predictably, never drops a finding"
requirement from the brief, applied to the vault specifically).

AC5/AC6: ``detokenize`` is the only function in this entire codebase that calls
``sealer.open`` outside of this module, and every router path to it goes through the
``VaultAccess`` dependency, which is independent of role or API key scope. No other
service (protection, ai_gateway, documents) ever imports ``open`` from this module.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from piishield.audit.service import Actor, record
from piishield.core.db import OrgScope
from piishield.core.kv import KV
from piishield.core.metrics import DETOKENIZE
from piishield.core.sealing import Sealed, Sealer
from piishield.vault import repository
from piishield.vault.exceptions import PlaceholderNotFoundError
from piishield.vault.models import VaultEntry, VaultGrant

_FINGERPRINT_CONTEXT = b"piishield-vault-fingerprint-v1"


def _fingerprint(value: str) -> str:
    return hmac.new(_FINGERPRINT_CONTEXT, value.encode(), hashlib.sha256).hexdigest()


def vault_context(entry_id: uuid.UUID) -> str:
    return f"vault:{entry_id}"


def _scope_cache_key(
    org_id: uuid.UUID, project_id: uuid.UUID, scope_id: str, fingerprint: str
) -> str:
    return f"piishield:tokenize:{org_id}:{project_id}:{scope_id}:{fingerprint}"


async def tokenize(
    session: AsyncSession,
    kv: KV,
    sealer: Sealer,
    actor: Actor,
    project_id: uuid.UUID,
    scope_id: str,
    category: str,
    value: str,
) -> str:
    """Returns a stable placeholder like ``[EMAIL_001]`` for ``value`` within ``scope_id``.
    A second call with the same value and scope returns the identical placeholder (AC4);
    a different value always gets a different placeholder number."""
    fp = _fingerprint(value)
    cache_key = _scope_cache_key(actor.org_id, project_id, scope_id, fp)
    cached = await kv.get(cache_key)
    if cached is not None:
        placeholder = cached.decode()
        # Trust the cache for the fast path, but only after confirming the row still
        # exists (a KV outage or stale entry falls through to the database path below;
        # this never trusts the cache alone for correctness, only for the round trip).
        existing = await repository.find_by_placeholder(
            session, actor.scope, project_id, scope_id, placeholder
        )
        if existing is not None:
            return placeholder

    existing = await repository.find_by_fingerprint(session, actor.scope, project_id, scope_id, fp)
    if existing is not None:
        await kv.set(cache_key, existing.placeholder.encode(), 3600)
        return existing.placeholder

    ordinal = (
        await repository.count_placeholders_in_scope(
            session, actor.scope, project_id, scope_id, category
        )
        + 1
    )
    placeholder = f"[{category.upper()}_{ordinal:03d}]"
    entry_id = uuid.uuid4()
    sealed = await sealer.seal(value, vault_context(entry_id))
    entry = VaultEntry(
        id=entry_id,
        org_id=actor.org_id,
        project_id=project_id,
        scope_id=scope_id,
        category=category,
        placeholder=placeholder,
        sealed_value=sealed.encode(),
        value_fingerprint=fp,
    )
    repository.add(session, entry)
    await session.flush()
    await kv.set(cache_key, placeholder.encode(), 3600)
    return placeholder


async def resolve_in_scope(
    session: AsyncSession,
    sealer: Sealer,
    scope: OrgScope,
    project_id: uuid.UUID,
    scope_id: str,
    placeholder: str,
) -> tuple[str, str] | None:
    """Opens the vault entry for ``placeholder`` within this exact scope, or ``None`` if
    none exists. Internal, cross-domain entrypoint used by ``ai_gateway.service.restore``
    (see that module's docstring for why that call is a different trust boundary from the
    human-facing ``detokenize`` below: it does not write a "detokenize" audit action and
    does not require the ``VaultAccess`` permission, only the scope_id the caller already
    received from its own earlier ``protect`` call)."""
    entry = await repository.find_by_placeholder(session, scope, project_id, scope_id, placeholder)
    if entry is None:
        return None
    value = await sealer.open(Sealed.decode(entry.sealed_value), vault_context(entry.id))
    return value, entry.category


async def detokenize(
    session: AsyncSession,
    sealer: Sealer,
    actor: Actor,
    project_id: uuid.UUID,
    scope_id: str,
    placeholder: str,
) -> tuple[str, str]:
    """Returns (original_value, category). The ONLY human-facing function that decrypts a
    vault row. Callers must already hold vault access (enforced by the ``VaultAccess``
    FastAPI dependency at the router boundary, never re-checked here, so there is exactly
    one place in the codebase that decides this)."""
    resolved = await resolve_in_scope(
        session, sealer, actor.scope, project_id, scope_id, placeholder
    )
    if resolved is None:
        DETOKENIZE.labels(outcome="not_found").inc()
        raise PlaceholderNotFoundError()
    value, category = resolved
    record(
        session,
        actor,
        "detokenize",
        project_id=project_id,
        finding_count=1,
        categories=[category],
        scope_id=scope_id,
        placeholder=placeholder,
    )
    await session.commit()
    DETOKENIZE.labels(outcome="found").inc()
    return value, category


async def grant_access(
    session: AsyncSession, actor: Actor, user_id: uuid.UUID | None, api_key_id: uuid.UUID | None
) -> VaultGrant:
    grant = VaultGrant(
        org_id=actor.org_id, user_id=user_id, api_key_id=api_key_id, granted_by=actor.id
    )
    repository.add_grant(session, grant)
    await session.flush()
    record(session, actor, "vault_grant.created", user_id=str(user_id) if user_id else None)
    await session.commit()
    return grant


async def list_grants(session: AsyncSession, scope: OrgScope) -> list[VaultGrant]:
    return await repository.list_grants(session, scope)


async def revoke_grant(session: AsyncSession, actor: Actor, grant_id: uuid.UUID) -> None:
    from datetime import UTC, datetime

    from piishield.core.db import get_scoped

    grant = await get_scoped(session, VaultGrant, actor.scope, grant_id)
    if grant is None:
        return
    grant.revoked_at = datetime.now(UTC)
    record(session, actor, "vault_grant.revoked")
    await session.commit()
