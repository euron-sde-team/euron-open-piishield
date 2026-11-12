"""Document scan records: counts, categories and a per-page/sheet breakdown, never a
value and never the document bytes themselves (those are not persisted at all; a document
scan is request-scoped, like text and JSON)."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from piishield.core.db import Base, OrgScoped, TimestampMixin, new_id


class DocumentScan(OrgScoped, TimestampMixin, Base):
    __tablename__ = "document_scans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    # pdf / docx / xlsx / csv
    file_type: Mapped[str] = mapped_column(String(8), nullable=False)
    finding_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    categories: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    # [{"page": 1, "finding_count": 3, "categories": [...]}] or [{"sheet": "Sheet1", ...}]
    breakdown: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False, default=list)
