"""Per-project policy: required categories, masking method per category, confidence
threshold, and retention. One row per project."""

from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from piishield.core.db import Base, OrgScoped, TimestampMixin, new_id

DEFAULT_METHOD = "tokenize"


class Policy(OrgScoped, TimestampMixin, Base):
    __tablename__ = "policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    # Categories that must always be protected regardless of confidence (AC10, AC13):
    # e.g. ["financial", "government_id"].
    required_categories: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    # category -> "full_mask" | "partial_mask" | "redact" | "tokenize". Categories absent
    # here use DEFAULT_METHOD.
    masking_method: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False, default=dict)
    # Number of characters a partial mask reveals (from the end of the value).
    partial_mask_reveal: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    # Findings below this confidence go to the review queue instead of being
    # auto-protected, unless their category is also required (AC10 + AC13).
    confidence_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.6)
    # Days vault entries and scan records are retained before they are eligible for purge.
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
