"""The only code that queries the database for document scan records."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from piishield.documents.models import DocumentScan


def record_scan(
    session: AsyncSession,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    filename: str,
    file_type: str,
    finding_count: int,
    categories: list[str],
    breakdown: list[dict[str, object]],
) -> DocumentScan:
    row = DocumentScan(
        org_id=org_id,
        project_id=project_id,
        filename=filename,
        file_type=file_type,
        finding_count=finding_count,
        categories=sorted(set(categories)),
        breakdown=breakdown,
    )
    session.add(row)
    return row
