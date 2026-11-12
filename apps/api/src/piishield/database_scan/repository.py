"""The only code that queries PIIShield's own database for scan results (row sampling
against the TARGET database being scanned lives in service.py, a different connection
entirely, never through this repository)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from piishield.database_scan.models import DatabaseScanResult


def record_scan(
    session: AsyncSession,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    table_name: str,
    rows_sampled: int,
    columns: list[dict[str, object]],
) -> DatabaseScanResult:
    row = DatabaseScanResult(
        org_id=org_id,
        project_id=project_id,
        table_name=table_name,
        rows_sampled=rows_sampled,
        columns=columns,
    )
    session.add(row)
    return row
