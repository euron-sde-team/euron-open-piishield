"""Audit log wire shapes."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class AuditEntryOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    actor_kind: str
    actor_label: str
    action: str
    project_id: uuid.UUID | None
    finding_count: int
    categories: list[str]
    details: dict[str, object]


class AuditPage(BaseModel):
    items: list[AuditEntryOut]
    next_cursor: str | None = None
