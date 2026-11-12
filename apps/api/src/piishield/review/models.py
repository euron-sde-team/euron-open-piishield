"""Low-confidence findings pending a human decision (AC13).

A review item never stores the matched text either: only category, span, confidence and
which scan it came from, consistent with AC11's "no original value anywhere but the
vault" rule, which applies here too even though this is not the vault.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from piishield.core.db import Base, OrgScoped, TimestampMixin, new_id


class ReviewItem(OrgScoped, TimestampMixin, Base):
    __tablename__ = "review_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    start: Mapped[int] = mapped_column(Integer, nullable=False)
    end: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    recognizer: Mapped[str] = mapped_column(String(64), nullable=False)
    # Already protected because the category is also "required" (AC10 forces protection
    # regardless of confidence); still flagged for review per PLAN.md's lifecycle step 3.
    already_protected: Mapped[bool] = mapped_column(nullable=False, default=False)
    # pending / approved / dismissed
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
