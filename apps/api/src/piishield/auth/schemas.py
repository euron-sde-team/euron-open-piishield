"""Auth wire shapes: signup, login, the session, and API key management."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignupIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    org_name: str = Field(..., min_length=1, max_length=120)
    name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(..., min_length=10, max_length=200)


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(..., max_length=200)


class SessionOut(BaseModel):
    token: str
    user: UserOut


class UserOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    email: str
    name: str
    role: str
    vault_access: bool


SessionOut.model_rebuild()


class ApiKeyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=120)
    scope: Literal["read", "write"] = "read"


class ApiKeyCreated(BaseModel):
    """Returned exactly once, at creation. The plaintext key is never retrievable again:
    only its prefix and hash are stored (matching the sibling project's API key pattern)."""

    id: uuid.UUID
    name: str
    prefix: str
    scope: str
    key: str


class ApiKeyOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    prefix: str
    scope: str
    revoked_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime
