"""Management API keys: one per project, peppered HMAC, never returned after creation."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from piishield.core.db import Base, OrgScoped, TimestampMixin, new_id


class ApiKey(OrgScoped, TimestampMixin, Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # 12 hex chars, looked up directly (never scanned linearly); the secret after it is
    # never stored, only its peppered HMAC.
    prefix: Mapped[str] = mapped_column(String(12), nullable=False, unique=True, index=True)
    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # read: scan/mask/redact/tokenize and read-only admin surfaces. write: also manage
    # policies, projects and keys. A key never implies vault access (AC5): that is its own
    # grant, recorded in vault.models.VaultGrant keyed by this key's id.
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default="read")
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
