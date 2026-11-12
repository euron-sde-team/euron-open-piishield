"""Vault wire shapes.

Note what is NOT here: there is no schema anywhere in this module that includes
``sealed_value`` or any field that could carry a decrypted original. ``DetokenizeOut`` is
the only response shape in the entire API that carries an original value, and only the
``VaultAccess`` dependency can reach the endpoint that returns it (AC6).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DetokenizeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: uuid.UUID
    placeholder: str = Field(..., min_length=1, max_length=64)
    scope_id: str = Field(..., min_length=1, max_length=200)


class DetokenizeOut(BaseModel):
    placeholder: str
    value: str
    category: str


class VaultGrantIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: uuid.UUID | None = None
    api_key_id: uuid.UUID | None = None


class VaultGrantOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    api_key_id: uuid.UUID | None
    revoked_at: datetime | None = None
