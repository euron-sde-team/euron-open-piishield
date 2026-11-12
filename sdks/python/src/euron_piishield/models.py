"""Typed results returned by the client.

These mirror the real wire format in ``apps/api/src/piishield`` (see the README's "Wire
format" section): ``protection/schemas.py``, ``vault/schemas.py``, ``ai_gateway/schemas.py``,
``detectors/schemas.py``, ``policies/schemas.py``, ``audit/schemas.py``,
``database_scan/schemas.py``, ``documents/schemas.py``, ``review/schemas.py``. Unknown
fields the API adds later are kept in ``raw`` on every model.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

MaskingMethod = Literal["full_mask", "partial_mask", "redact", "tokenize"]


@dataclass(frozen=True)
class Finding:
    """One detected value: what it is, where it is, how confident PIIShield is, and what
    was done to it. Matches ``protection.schemas.ProtectedFindingOut``.

    Never carries the original matched value: PIIShield's own server-side contract
    (AC6, AC11) returns the original value only from an authorized ``detokenize`` call,
    never from ``protect``, a document, the AI gateway, or the audit log.
    """

    category: str
    start: int
    end: int
    confidence: float
    checksum_valid: bool | None
    recognizer: str
    method: str
    placeholder: str | None = None
    in_review: bool = False
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> Finding:
        return cls(
            category=str(data.get("category", "")),
            start=int(data.get("start", 0) or 0),
            end=int(data.get("end", 0) or 0),
            confidence=float(data.get("confidence") or 0.0),
            checksum_valid=data.get("checksum_valid"),
            recognizer=str(data.get("recognizer", "")),
            method=str(data.get("method", "")),
            placeholder=data.get("placeholder"),
            in_review=bool(data.get("in_review", False)),
            raw=dict(data),
        )


@dataclass(frozen=True)
class ScanResult:
    """The result of ``scan``: what was found, nothing changed.

    ``scan`` calls the dedicated ``POST /api/v1/detectors/scan`` route: detection only,
    no protection applied and no audit entry written, unlike ``protect``/``mask``. See
    the README's "Wire format" section, point 1.
    """

    findings: list[Finding] = field(default_factory=list)
    review_count: int = 0
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> ScanResult:
        return cls(
            findings=[Finding.from_api(f) for f in data.get("findings") or []],
            review_count=int(data.get("review_count") or 0),
            raw=dict(data),
        )


@dataclass(frozen=True)
class ProtectionResult:
    """The output of ``mask`` / ``redact`` / ``anonymize`` / ``tokenize`` on text.
    Matches ``protection.schemas.ProtectTextOut``.
    """

    protected_text: str
    findings: list[Finding] = field(default_factory=list)
    review_count: int = 0
    scope_id: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> ProtectionResult:
        return cls(
            protected_text=str(data.get("protected", "")),
            findings=[Finding.from_api(f) for f in data.get("findings") or []],
            review_count=int(data.get("review_count") or 0),
            scope_id=str(data.get("scope_id", "")),
            raw=dict(data),
        )


@dataclass(frozen=True)
class ProtectionJsonResult:
    """The output of a ``mask``/``redact``/``anonymize``/``tokenize`` call on JSON.
    Matches ``protection.schemas.ProtectJsonOut``. ``protected_json`` preserves the exact
    input structure (same keys, nesting, array order): only leaf string values change
    (AC7 of docs/PLAN.md).
    """

    protected_json: Any
    findings: list[Finding] = field(default_factory=list)
    review_count: int = 0
    scope_id: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> ProtectionJsonResult:
        return cls(
            protected_json=data.get("protected"),
            findings=[Finding.from_api(f) for f in data.get("findings") or []],
            review_count=int(data.get("review_count") or 0),
            scope_id=str(data.get("scope_id", "")),
            raw=dict(data),
        )


@dataclass(frozen=True)
class DetokenizeResult:
    """The result of an authorized ``detokenize`` call. Matches
    ``vault.schemas.DetokenizeOut``: ``{"placeholder", "value", "category"}``.

    Only ever returned to a caller holding the vault-access grant; everyone else gets
    :class:`~euron_piishield.errors.VaultPermissionError` instead of this object.
    """

    placeholder: str
    value: str
    category: str
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> DetokenizeResult:
        return cls(
            placeholder=str(data.get("placeholder", "")),
            value=str(data.get("value", "")),
            category=str(data.get("category", "")),
            raw=dict(data),
        )


@dataclass(frozen=True)
class ProtectResult:
    """The output of the AI gateway's ``protect`` call. Matches
    ``ai_gateway.schemas.GatewayProtectOut``.

    ``protected_text`` is the only field meant to reach the external model. ``scope_id``
    is the other half: it must stay with the caller (or the calling application's own
    server) and be presented back to ``restore`` after the model responds. Never combine
    the two into one payload handed to the model provider.
    """

    protected_text: str
    scope_id: str
    findings: list[Finding] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> ProtectResult:
        return cls(
            protected_text=str(data.get("protected_prompt", "")),
            scope_id=str(data.get("scope_id", "")),
            findings=[Finding.from_api(f) for f in data.get("findings") or []],
            raw=dict(data),
        )


@dataclass(frozen=True)
class RestoreResult:
    """The output of the AI gateway's ``restore`` call. Matches
    ``ai_gateway.schemas.GatewayRestoreOut``.

    ``restored_text`` is for the calling application only: the external model that
    produced ``model_response_text`` never sees this.
    """

    restored_text: str
    placeholders_restored: int = 0
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> RestoreResult:
        return cls(
            restored_text=str(data.get("restored_response", "")),
            placeholders_restored=int(data.get("placeholders_restored") or 0),
            raw=dict(data),
        )


@dataclass(frozen=True)
class Policy:
    """A project's policy. Matches ``policies.schemas.PolicyOut``."""

    id: str
    project_id: str
    required_categories: list[str] = field(default_factory=list)
    masking_method: dict[str, MaskingMethod] = field(default_factory=dict)
    partial_mask_reveal: int = 4
    confidence_threshold: float = 0.6
    retention_days: int = 90
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> Policy:
        return cls(
            id=str(data.get("id", "")),
            project_id=str(data.get("project_id", "")),
            required_categories=list(data.get("required_categories") or []),
            masking_method=dict(data.get("masking_method") or {}),
            partial_mask_reveal=int(data.get("partial_mask_reveal") or 4),
            confidence_threshold=float(data.get("confidence_threshold") or 0.6),
            retention_days=int(data.get("retention_days") or 90),
            raw=dict(data),
        )


@dataclass(frozen=True)
class AuditLogEntry:
    """One row of the append-only audit log. Matches ``audit.schemas.AuditEntryOut``.
    Never carries an original sensitive value (AC11).
    """

    id: str
    created_at: str | None
    actor_kind: str
    actor_label: str
    action: str
    project_id: str | None
    finding_count: int = 0
    categories: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> AuditLogEntry:
        return cls(
            id=str(data.get("id", "")),
            created_at=data.get("created_at"),
            actor_kind=str(data.get("actor_kind", "")),
            actor_label=str(data.get("actor_label", "")),
            action=str(data.get("action", "")),
            project_id=data.get("project_id"),
            finding_count=int(data.get("finding_count") or 0),
            categories=list(data.get("categories") or []),
            details=dict(data.get("details") or {}),
            raw=dict(data),
        )


@dataclass(frozen=True)
class AuditLogPage:
    """A page of the audit log. Matches ``audit.schemas.AuditPage``."""

    items: list[AuditLogEntry] = field(default_factory=list)
    next_cursor: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> AuditLogPage:
        return cls(
            items=[AuditLogEntry.from_api(e) for e in data.get("items") or []],
            next_cursor=data.get("next_cursor"),
            raw=dict(data),
        )


@dataclass(frozen=True)
class ColumnFinding:
    """One column's PII likelihood from a database scan."""

    column: str
    category: str
    confidence: float
    sample_hits: int

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> ColumnFinding:
        return cls(
            column=str(data.get("column", "")),
            category=str(data.get("category", "")),
            confidence=float(data.get("confidence") or 0.0),
            sample_hits=int(data.get("sample_hits") or 0),
        )


@dataclass(frozen=True)
class DatabaseScanResult:
    """A read-only, column-level scan of a provided database connection. Matches
    ``database_scan.schemas.DatabaseScanOut``.
    """

    id: str
    table_name: str
    rows_sampled: int
    columns: list[ColumnFinding] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> DatabaseScanResult:
        return cls(
            id=str(data.get("id", "")),
            table_name=str(data.get("table_name", "")),
            rows_sampled=int(data.get("rows_sampled") or 0),
            columns=[ColumnFinding.from_api(c) for c in data.get("columns") or []],
            raw=dict(data),
        )


@dataclass(frozen=True)
class DocumentScanReport:
    """The metadata response alongside a protected document upload. Matches
    ``documents.schemas.DocumentScanReport``. The protected file itself is returned as a
    separate binary body with the original content type, not embedded here.
    """

    id: str
    filename: str
    file_type: str
    finding_count: int
    categories: list[str] = field(default_factory=list)
    breakdown: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> DocumentScanReport:
        return cls(
            id=str(data.get("id", "")),
            filename=str(data.get("filename", "")),
            file_type=str(data.get("file_type", "")),
            finding_count=int(data.get("finding_count") or 0),
            categories=list(data.get("categories") or []),
            breakdown=list(data.get("breakdown") or []),
            raw=dict(data),
        )


@dataclass(frozen=True)
class ReviewItem:
    """One pending low-confidence finding. Matches ``review.schemas.ReviewItemOut``."""

    id: str
    project_id: str
    category: str
    start: int
    end: int
    confidence: float
    recognizer: str
    already_protected: bool
    status: str
    created_at: str | None
    decided_at: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> ReviewItem:
        return cls(
            id=str(data.get("id", "")),
            project_id=str(data.get("project_id", "")),
            category=str(data.get("category", "")),
            start=int(data.get("start", 0) or 0),
            end=int(data.get("end", 0) or 0),
            confidence=float(data.get("confidence") or 0.0),
            recognizer=str(data.get("recognizer", "")),
            already_protected=bool(data.get("already_protected", False)),
            status=str(data.get("status", "")),
            created_at=data.get("created_at"),
            decided_at=data.get("decided_at"),
            raw=dict(data),
        )
