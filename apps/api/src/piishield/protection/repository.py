"""The only code that queries the database for scan events."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from piishield.protection.models import ScanEvent


def add(session: AsyncSession, event: ScanEvent) -> None:
    session.add(event)


def record_scan(
    session: AsyncSession,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    source: str,
    finding_count: int,
    review_count: int,
    categories: list[str],
) -> ScanEvent:
    event = ScanEvent(
        org_id=org_id,
        project_id=project_id,
        source=source,
        finding_count=finding_count,
        review_count=review_count,
        categories=sorted(set(categories)),
    )
    add(session, event)
    return event
