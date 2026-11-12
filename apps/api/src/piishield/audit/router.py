"""The append-only audit log, read-only."""

from __future__ import annotations

from fastapi import APIRouter

from piishield.audit import service
from piishield.audit.schemas import AuditEntryOut, AuditPage
from piishield.auth.dependencies import StaffRead
from piishield.core.deps import SessionDep

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("", response_model=AuditPage, summary="List audit log entries")
async def list_audit(
    actor: StaffRead, session: SessionDep, limit: int = 50, action: str | None = None
) -> AuditPage:
    rows = await service.list_entries(session, actor.scope, limit=limit, action=action)
    return AuditPage(
        items=[
            AuditEntryOut(
                id=r.id,
                created_at=r.created_at,
                actor_kind=r.actor_kind,
                actor_label=r.actor_label,
                action=r.action,
                project_id=r.project_id,
                finding_count=r.finding_count,
                categories=r.categories,
                details=r.details,
            )
            for r in rows
        ],
        next_cursor=None,
    )
