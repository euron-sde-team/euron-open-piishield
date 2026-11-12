"""Review queue wire shapes."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ReviewItemOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    category: str
    start: int
    end: int
    confidence: float
    recognizer: str
    already_protected: bool
    status: str
    created_at: datetime
    decided_at: datetime | None
