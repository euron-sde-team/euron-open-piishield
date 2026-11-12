"""Append-only audit log.

AC11: a record carries counts and categories, never an original sensitive value or a
vault mapping's plaintext. ``details`` is a small JSON document whose shape is restricted
at the call site (``audit.service.record``); nothing passes a raw finding value into it.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from piishield.core.db import Base, OrgScoped, new_id


class AuditLog(OrgScoped, Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    # user / api_key / system
    actor_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    actor_label: Mapped[str] = mapped_column(String(255), nullable=False)
    # scan / mask / redact / tokenize / detokenize / policy.updated / review.* / key.* / ...
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    # Counts and categories only; see the module docstring and audit.service.record.
    finding_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    categories: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    details: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
