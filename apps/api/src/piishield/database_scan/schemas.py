"""Database scan wire shapes.

The connection string is accepted only as a request field, used once to sample rows, and
never stored (not in the scan result row, not in the audit log): only ``table_name``
(caller-supplied, used as a label) and the column findings are persisted.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DatabaseScanIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: uuid.UUID
    engine: Literal["postgres", "mysql", "sqlite"]
    connection_string: str = Field(..., max_length=2000)
    table_name: str = Field(..., min_length=1, max_length=255)
    sample_rows: int = Field(200, ge=1, le=5000)


class ColumnFinding(BaseModel):
    column: str
    category: str
    confidence: float
    sample_hits: int


class DatabaseScanOut(BaseModel):
    id: uuid.UUID
    table_name: str
    rows_sampled: int
    columns: list[ColumnFinding]
