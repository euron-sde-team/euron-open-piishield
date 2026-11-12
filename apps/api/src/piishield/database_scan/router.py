"""Read-only column-level database scan."""

from __future__ import annotations

from fastapi import APIRouter

from piishield.auth.dependencies import StaffWrite
from piishield.core.deps import SessionDep
from piishield.database_scan import service
from piishield.database_scan.schemas import DatabaseScanIn, DatabaseScanOut

router = APIRouter(prefix="/api/v1/database-scan", tags=["database_scan"])


@router.post(
    "", response_model=DatabaseScanOut, summary="Sample a table and report likely-PII columns"
)
async def scan_table(
    body: DatabaseScanIn, actor: StaffWrite, session: SessionDep
) -> DatabaseScanOut:
    result_id, rows_sampled, columns = await service.scan_table(
        session,
        actor,
        body.project_id,
        body.engine,
        body.connection_string,
        body.table_name,
        body.sample_rows,
    )
    return DatabaseScanOut(
        id=result_id, table_name=body.table_name, rows_sampled=rows_sampled, columns=columns
    )
