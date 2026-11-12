"""Protection wire shapes: the text/JSON protect endpoints and their shared finding shape.

Wire contract notes for SDK authors (AC14): every protect response has the same top-level
shape regardless of method (``full_mask``/``partial_mask``/``redact``/``tokenize``):
``{"protected": <str|object>, "findings": [...], "review_count": int, "scope_id":
str|null}``. ``findings`` never contains the original value or the vault's ciphertext,
only ``category``, ``start``, ``end``, ``confidence``, ``checksum_valid``, ``method``,
``placeholder`` (tokenize only, null otherwise) and ``recognizer``.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MaskingMethod = Literal["full_mask", "partial_mask", "redact", "tokenize"]


class ProtectedFindingOut(BaseModel):
    category: str
    start: int
    end: int
    confidence: float
    checksum_valid: bool | None
    recognizer: str
    method: str
    placeholder: str | None = None
    in_review: bool = False


class ProtectTextIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: uuid.UUID
    text: str = Field(..., max_length=2_000_000)
    # Per-category override of the policy's default method for this call only.
    method_overrides: dict[str, MaskingMethod] = Field(default_factory=dict)
    # Categories this call explicitly requests to leave unmasked (checked against the
    # policy's required_categories; AC10 refuses if any of these is required).
    skip_categories: list[str] = Field(default_factory=list)
    # A request id or named session for scope-consistent tokenization (AC4). Defaults to
    # a fresh id per call when omitted, so tokenize is still internally consistent within
    # one call even without an explicit scope.
    scope_id: str | None = Field(None, max_length=200)


class ProtectTextOut(BaseModel):
    protected: str
    findings: list[ProtectedFindingOut]
    review_count: int
    scope_id: str


class ProtectJsonIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: uuid.UUID
    payload: object
    method_overrides: dict[str, MaskingMethod] = Field(default_factory=dict)
    skip_categories: list[str] = Field(default_factory=list)
    scope_id: str | None = Field(None, max_length=200)


class ProtectJsonOut(BaseModel):
    protected: object
    findings: list[ProtectedFindingOut]
    review_count: int
    scope_id: str
