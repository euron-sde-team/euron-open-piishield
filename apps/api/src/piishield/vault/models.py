"""The encrypted mapping store: the only place an original value is ever recoverable from
a placeholder (``[EMAIL_001]``), and the vault access grant that is a permission separate
from any admin/owner role or write-scoped API key (AC5)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from piishield.core.db import Base, OrgScoped, TimestampMixin, new_id


class VaultEntry(OrgScoped, TimestampMixin, Base):
    """One tokenized value. ``sealed_value`` is the AES-256-GCM ciphertext (see
    core.sealing); the plaintext never exists anywhere else once this row is written."""

    __tablename__ = "vault_entries"
    __table_args__ = (
        UniqueConstraint("org_id", "scope_id", "placeholder", name="uq_vault_scope_placeholder"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # A request id or a named session: the boundary within which the same input value
    # always maps to the same placeholder (AC4).
    scope_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    # e.g. "[EMAIL_001]". Stable per (scope_id, value) pair.
    placeholder: Mapped[str] = mapped_column(String(64), nullable=False)
    # AES-256-GCM ciphertext, base64, sealed under this row's own id as AEAD context.
    sealed_value: Mapped[str] = mapped_column(String(4000), nullable=False)
    # A deterministic, salted hash of the plaintext (never the plaintext, never reversible
    # on its own) so a second tokenize() call for the same value in the same scope can
    # find its existing placeholder without decrypting anything.
    value_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class VaultGrant(OrgScoped, TimestampMixin, Base):
    """AC5: detokenization needs this grant, which is independent of role and of API key
    scope. Granted to a user or to an API key (exactly one of the two is set)."""

    __tablename__ = "vault_grants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    api_key_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("api_keys.id", ondelete="CASCADE"), nullable=True
    )
    granted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
