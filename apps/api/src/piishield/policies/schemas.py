"""Policy wire shapes."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MaskingMethod = Literal["full_mask", "partial_mask", "redact", "tokenize"]


class PolicyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    required_categories: list[str] = Field(default_factory=list)
    masking_method: dict[str, MaskingMethod] = Field(default_factory=dict)
    partial_mask_reveal: int = Field(4, ge=0, le=32)
    confidence_threshold: float = Field(0.6, ge=0.0, le=1.0)
    retention_days: int = Field(90, ge=1, le=3650)


class PolicyOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    required_categories: list[str]
    masking_method: dict[str, str]
    partial_mask_reveal: int
    confidence_threshold: float
    retention_days: int
