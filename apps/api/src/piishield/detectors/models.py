"""Per-project custom pattern recognizers (PLAN.md: "a custom-pattern recognizer per
project")."""

from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from piishield.core.db import Base, OrgScoped, TimestampMixin, new_id


class CustomRecognizer(OrgScoped, TimestampMixin, Base):
    __tablename__ = "recognizers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    pattern: Mapped[str] = mapped_column(String(2000), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
