"""Read-only, column-level database scan results (PLAN.md's 0.1.0 scope: sample rows,
report which columns look like they hold PII, never write back to the scanned database)."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from piishield.core.db import Base, OrgScoped, TimestampMixin, new_id


class DatabaseScanResult(OrgScoped, TimestampMixin, Base):
    __tablename__ = "database_scan_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # The host/db/table the caller supplied; never the connection credentials (those are
    # provided per call and never persisted, see service.py).
    table_name: Mapped[str] = mapped_column(String(255), nullable=False)
    rows_sampled: Mapped[int] = mapped_column(Integer, nullable=False)
    # [{"column": "email", "category": "contact", "confidence": 0.9, "sample_hits": 8}]
    columns: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False, default=list)
