"""Builders for mocked PIIShield API responses."""

from __future__ import annotations

from typing import Any

BASE = "http://piishield.test"
API_KEY = "pii_" + "k" * 10 + "_" + "s" * 30
PROJECT_ID = "83bf425d-2fe8-4a56-8845-70ba8ea89211"


def finding(
    category: str, start: int, end: int, confidence: float = 0.9, **extra: Any
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "category": category,
        "start": start,
        "end": end,
        "confidence": confidence,
        "checksum_valid": None,
        "recognizer": f"{category}_recognizer",
        "method": "full_mask",
        "placeholder": None,
        "in_review": False,
    }
    body.update(extra)
    return body


def scan_response(*findings: dict[str, Any], review_count: int = 0) -> dict[str, Any]:
    """Matches ``detectors.schemas.ScanResultOut``: no ``protected``/``scope_id``,
    unlike ``protect_text_response`` (the ``/api/v1/detectors/scan`` route this backs
    never applies protection)."""
    return {"findings": list(findings), "review_count": review_count}


def protect_text_response(
    protected: str, *findings: dict[str, Any], review_count: int = 0, scope_id: str = "scope-1"
) -> dict[str, Any]:
    return {
        "protected": protected,
        "findings": list(findings),
        "review_count": review_count,
        "scope_id": scope_id,
    }


def error_body(
    code: str, message: str = "error", details: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "error": {"code": code, "type": "some_error", "message": message, "details": details or {}}
    }
