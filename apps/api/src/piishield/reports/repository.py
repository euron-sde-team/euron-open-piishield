"""The only code that queries the database for report aggregates.

Deliberately reads only the counts-and-categories tables (``scan_events``,
``review_items``, ``vault_entries``'s row count): never a value, consistent with every
other reporting surface in this program.
"""

from __future__ import annotations

from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from piishield.core.db import OrgScope
from piishield.protection.models import ScanEvent
from piishield.review.models import ReviewItem
from piishield.vault.models import VaultEntry


async def totals(session: AsyncSession, scope: OrgScope) -> tuple[int, int]:
    stmt = select(func.count(), func.coalesce(func.sum(ScanEvent.finding_count), 0)).where(
        ScanEvent.org_id == scope.org_id
    )
    row = (await session.execute(stmt)).one()
    return int(row[0]), int(row[1])


async def pending_review_count(session: AsyncSession, scope: OrgScope) -> int:
    stmt = select(func.count()).where(
        ReviewItem.org_id == scope.org_id, ReviewItem.status == "pending"
    )
    return int((await session.scalar(stmt)) or 0)


async def findings_by_category(session: AsyncSession, scope: OrgScope) -> list[tuple[str, int]]:
    """Aggregated in Python over each scan event's small ``categories`` list (bounded by
    event count, not by finding count): simple and provably correct for 0.1.0's scale;
    a pre-aggregated rollup table is the natural optimisation if this read becomes hot."""
    stmt = select(ScanEvent.categories).where(ScanEvent.org_id == scope.org_id)
    counts: Counter[str] = Counter()
    for (categories,) in (await session.execute(stmt)).all():
        counts.update(categories)
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


async def vault_entry_count(session: AsyncSession, scope: OrgScope) -> int:
    stmt = select(func.count()).where(VaultEntry.org_id == scope.org_id)
    return int((await session.scalar(stmt)) or 0)
