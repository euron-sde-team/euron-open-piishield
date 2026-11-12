"""Organizations and the users (people) who belong to them.

Roles: ``owner``, ``admin``, ``viewer``, plus a dedicated ``vault_access`` boolean that is
granted separately from any role (AC5). An owner or admin does NOT automatically get vault
access: detokenization needs an explicit grant, checked in ``vault.service``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from piishield.core.db import Base, OrgScoped, TimestampMixin, new_id


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)


class User(OrgScoped, TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # owner: full control including inviting admins. admin: manage projects/policies/keys.
    # viewer: read-only (scans, reports, audit log, review queue) but no vault access ever
    # implied by role alone.
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="viewer")
    # A permission separate from role: only a user (or API key, see auth.models.ApiKey)
    # with this set to true may call vault.detokenize (AC5).
    vault_access: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Bumped on password change so existing sessions stop working immediately.
    session_version: Mapped[int] = mapped_column(nullable=False, default=0)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RevokedSession(Base):
    """Signed-out session ids, kept until they would have expired anyway."""

    __tablename__ = "revoked_sessions"

    jti: Mapped[str] = mapped_column(String(32), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
