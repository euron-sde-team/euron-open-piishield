"""Document wire shapes (the metadata response; the protected file itself is returned as
a binary body with the original content type, not embedded in JSON)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class DocumentScanReport(BaseModel):
    id: uuid.UUID
    filename: str
    file_type: str
    finding_count: int
    categories: list[str]
    breakdown: list[dict[str, object]]
