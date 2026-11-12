"""Detector wire shapes."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class FindingOut(BaseModel):
    category: str
    start: int
    end: int
    confidence: float
    checksum_valid: bool | None
    recognizer: str


class ScanTextIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: uuid.UUID
    text: str = Field(..., min_length=0, max_length=2_000_000)


class ScanResultOut(BaseModel):
    findings: list[FindingOut]
    review_count: int


class CustomRecognizerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=80)
    category: str = Field(..., min_length=1, max_length=32)
    pattern: str = Field(..., min_length=1, max_length=2000)
    confidence: float = Field(0.7, ge=0.0, le=1.0)


class CustomRecognizerOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    category: str
    pattern: str
    confidence: float
    enabled: bool
