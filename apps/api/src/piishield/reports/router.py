"""Dashboard summary report."""

from __future__ import annotations

from fastapi import APIRouter

from piishield.auth.dependencies import StaffRead
from piishield.core.deps import ContainerDep, SessionDep
from piishield.reports import service
from piishield.reports.schemas import SummaryReport

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/summary", response_model=SummaryReport, summary="Scan and finding totals for the org")
async def get_summary(
    actor: StaffRead, container: ContainerDep, session: SessionDep
) -> SummaryReport:
    return await service.summary(session, container.kv, actor.scope)
