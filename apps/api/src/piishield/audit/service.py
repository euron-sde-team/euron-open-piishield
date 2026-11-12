"""Who did what: the ``Actor`` every domain service receives, and the append-only log.

``record()`` is the ONLY way an audit row is written. Its signature deliberately has no
parameter for a raw value: callers pass ``finding_count`` and ``categories`` (strings like
``"financial"``, ``"government_id"``), never the finding's matched text. This is what makes
AC11 true by construction rather than by code review: there is no code path from a
detector's match back into an audit row. ``details`` additionally passes through
``_sanitize_details`` which drops or redacts any key that looks like it could hold a value.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from piishield.audit.models import AuditLog
from piishield.core.db import OrgScope, new_id

_VALUE_LIKE_KEYS = {
    "value",
    "original_value",
    "plaintext",
    "raw",
    "text",
    "content",
    "password",
    "secret",
    "secret_hash",
    "token",
    "api_key",
    "ciphertext",
}


@dataclass(frozen=True, slots=True)
class Actor:
    """Who did something: a person (by role) or a management API key. Always within one
    organization."""

    org_id: uuid.UUID
    id: uuid.UUID | None
    label: str
    role: str
    kind: str = "user"

    @property
    def scope(self) -> OrgScope:
        return OrgScope(self.org_id)


def system_actor(org_id: uuid.UUID, name: str = "system") -> Actor:
    return Actor(org_id, None, name, "system", kind="system")


def _sanitize_details(details: dict[str, Any]) -> dict[str, Any]:
    """Drop any key that could plausibly carry a real value instead of a count or label."""
    out: dict[str, Any] = {}
    for key, value in details.items():
        if key.lower() in _VALUE_LIKE_KEYS:
            continue
        if isinstance(value, dict):
            out[key] = _sanitize_details(value)
        else:
            out[key] = value
    return out


def record(
    session: AsyncSession,
    actor: Actor,
    action: str,
    *,
    project_id: uuid.UUID | None = None,
    finding_count: int = 0,
    categories: list[str] | None = None,
    **details: Any,
) -> AuditLog:
    """Add an audit row to the caller's session, so it commits (or rolls back) with the
    change it describes. Synchronous: it only stages the INSERT; a per-org sequence number
    is assigned by a scalar subquery so entries from one organization are consistently
    ordered even under concurrent writers."""
    from sqlalchemy import select as _select

    next_seq = (
        _select(func.coalesce(func.max(AuditLog.seq), 0) + 1)
        .where(AuditLog.org_id == actor.org_id)
        .scalar_subquery()
    )
    entry = AuditLog(
        id=new_id(),
        org_id=actor.org_id,
        seq=next_seq,
        actor_kind=actor.kind,
        actor_id=actor.id,
        actor_label=actor.label,
        action=action,
        project_id=project_id,
        finding_count=finding_count,
        categories=sorted(set(categories or [])),
        details=_sanitize_details(details),
    )
    session.add(entry)
    return entry


async def list_entries(
    session: AsyncSession, scope: OrgScope, *, limit: int = 50, action: str | None = None
) -> list[AuditLog]:
    stmt = (
        select(AuditLog)
        .where(AuditLog.org_id == scope.org_id)
        .order_by(AuditLog.seq.desc())
        .limit(min(limit, 200))
    )
    if action:
        stmt = stmt.where(AuditLog.action == action)
    return list((await session.scalars(stmt)).all())
