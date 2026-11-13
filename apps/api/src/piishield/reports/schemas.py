"""Reports wire shapes: dashboard aggregates over scan/document/gateway events."""

from __future__ import annotations

from pydantic import BaseModel


class CategoryCount(BaseModel):
    category: str
    count: int


class SummaryReport(BaseModel):
    total_scans: int
    total_findings: int
    pending_review: int
    findings_by_category: list[CategoryCount]
    vault_entries: int
