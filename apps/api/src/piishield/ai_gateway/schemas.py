"""AI gateway wire shapes.

Wire contract for SDK authors (AC14): ``protect`` returns ``protected_prompt`` (the text
to actually send to the external model) and ``scope_id`` (an opaque reference the SAME
caller later passes to ``restore`` along with the model's raw response text). The external
model never sees ``scope_id`` and never receives a restore call; only the calling
application, which already holds ``scope_id`` from the protect response, can restore.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from piishield.protection.schemas import ProtectedFindingOut


class GatewayProtectIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: uuid.UUID
    prompt: str = Field(..., max_length=2_000_000)
    scope_id: str | None = Field(None, max_length=200)


class GatewayProtectOut(BaseModel):
    protected_prompt: str
    findings: list[ProtectedFindingOut]
    scope_id: str


class GatewayRestoreIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: uuid.UUID
    scope_id: str = Field(..., max_length=200)
    model_response: str = Field(..., max_length=2_000_000)


class GatewayRestoreOut(BaseModel):
    restored_response: str
    placeholders_restored: int
