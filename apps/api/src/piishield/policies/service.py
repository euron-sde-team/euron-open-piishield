"""Policy load/update, with the project-policy cache documented in PLAN.md.

Caching: a read-through, in-process cache keyed by project id, TTL 5 seconds by default
(``settings.policy_cache_ttl_s``). Every admin write bumps a per-project version stamp in
the KV backend (Redis if configured, else this process's own memory); a cache hit is only
used when its stored version still matches the current stamp, so one replica's write is
visible to every replica within the TTL even without a pub/sub invalidation channel. This
is deliberately a bounded staleness window, not instant invalidation: a policy flip (e.g.
disabling masking for a required category, which AC10 would then refuse) can lag by up to
the TTL on other replicas, which is acceptable for a confidence threshold / masking
method setting and documented here and in docs/architecture/HLD.md.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from piishield.audit.service import Actor, record
from piishield.core.db import OrgScope
from piishield.core.kv import KV
from piishield.policies import repository
from piishield.policies.exceptions import PolicyNotFoundError
from piishield.policies.models import Policy
from piishield.policies.schemas import PolicyIn
from piishield.projects.service import ensure_project

_VERSION_PREFIX = "piishield:policy_version:"


@dataclass(frozen=True, slots=True)
class PolicySnapshot:
    id: uuid.UUID
    project_id: uuid.UUID
    required_categories: frozenset[str]
    masking_method: dict[str, str]
    partial_mask_reveal: int
    confidence_threshold: float
    retention_days: int

    def method_for(self, category: str) -> str:
        return self.masking_method.get(category, "tokenize")

    def is_required(self, category: str) -> bool:
        return category in self.required_categories


def _to_snapshot(policy: Policy) -> PolicySnapshot:
    return PolicySnapshot(
        id=policy.id,
        project_id=policy.project_id,
        required_categories=frozenset(policy.required_categories),
        masking_method=dict(policy.masking_method),
        partial_mask_reveal=policy.partial_mask_reveal,
        confidence_threshold=policy.confidence_threshold,
        retention_days=policy.retention_days,
    )


_DEFAULT = PolicySnapshot(
    id=uuid.UUID(int=0),
    project_id=uuid.UUID(int=0),
    required_categories=frozenset(),
    masking_method={},
    partial_mask_reveal=4,
    confidence_threshold=0.6,
    retention_days=90,
)

_local_cache: dict[uuid.UUID, tuple[float, int, PolicySnapshot]] = {}


async def bump(kv: KV, project_id: uuid.UUID) -> None:
    """Called by every policy write. Readers compare their cached version to this."""
    await kv.incr(f"{_VERSION_PREFIX}{project_id}")


async def _current_version(kv: KV, project_id: uuid.UUID) -> int:
    raw = await kv.get(f"{_VERSION_PREFIX}{project_id}")
    return int(raw) if raw else 0


async def load(
    session: AsyncSession, kv: KV, scope: OrgScope, project_id: uuid.UUID, *, fresh: bool = False
) -> PolicySnapshot:
    """A project's policy, or the built-in default if none was created yet (0.1.0's
    default: nothing required, tokenize everything, 0.6 confidence threshold)."""
    now = time.monotonic()
    version = await _current_version(kv, project_id)
    cached = _local_cache.get(project_id)
    if not fresh and cached is not None:
        cached_at, cached_version, snapshot = cached
        if cached_version == version and now - cached_at < 5.0:
            return snapshot
    row = await repository.get_for_project(session, scope, project_id)
    snapshot = _to_snapshot(row) if row is not None else _DEFAULT
    if len(_local_cache) > 10_000:
        _local_cache.clear()
    _local_cache[project_id] = (now, version, snapshot)
    return snapshot


def forget(project_id: uuid.UUID) -> None:
    _local_cache.pop(project_id, None)


async def upsert(
    session: AsyncSession, kv: KV, actor: Actor, project_id: uuid.UUID, body: PolicyIn
) -> Policy:
    """AC12: a policy is always attached to a project the caller's own org owns. Without
    this check, PUTing a policy for another org's project_id would silently create a new
    row (since no policy exists yet for THIS org at that project_id) rather than 404,
    which would let one org create a dangling policy keyed to a project it does not own."""
    await ensure_project(session, actor.scope, project_id)
    row = await repository.get_for_project(session, actor.scope, project_id)
    if row is None:
        row = Policy(org_id=actor.org_id, project_id=project_id)
        repository.add(session, row)
    row.required_categories = body.required_categories
    row.masking_method = dict(body.masking_method)
    row.partial_mask_reveal = body.partial_mask_reveal
    row.confidence_threshold = body.confidence_threshold
    row.retention_days = body.retention_days
    record(
        session,
        actor,
        "policy.updated",
        project_id=project_id,
        required_categories=body.required_categories,
    )
    await session.commit()
    await bump(kv, project_id)
    forget(project_id)
    return row


async def get_or_404(session: AsyncSession, scope: OrgScope, project_id: uuid.UUID) -> Policy:
    row = await repository.get_for_project(session, scope, project_id)
    if row is None:
        raise PolicyNotFoundError()
    return row
