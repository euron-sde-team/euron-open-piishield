"""Append-only scan event records: counts and categories only (never a value), used for
the dashboard aggregates and for report rollups."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from piishield.core.db import Base, OrgScoped, TimestampMixin, new_id


class ScanEvent(OrgScoped, TimestampMixin, Base):
    __tablename__ = "scan_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # text / json / document / ai_gateway_protect / ai_gateway_restore
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    finding_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    categories: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
