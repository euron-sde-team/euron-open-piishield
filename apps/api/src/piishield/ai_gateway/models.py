"""AI gateway call records: counts only, never the prompt or response text."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from piishield.core.db import Base, OrgScoped, TimestampMixin, new_id


class GatewayCall(OrgScoped, TimestampMixin, Base):
    __tablename__ = "ai_gateway_calls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scope_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    # protect / restore
    stage: Mapped[str] = mapped_column(String(16), nullable=False)
    finding_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    categories: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
