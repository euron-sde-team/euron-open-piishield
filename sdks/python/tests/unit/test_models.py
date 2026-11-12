"""Model parsing: defaults, unknown-field tolerance, the safety-relevant separations."""

from __future__ import annotations

from euron_piishield.models import Finding, ProtectionResult, ProtectResult, ScanResult


def test_finding_from_api_parses_all_fields() -> None:
    f = Finding.from_api(
        {
            "category": "email",
            "start": 1,
            "end": 5,
            "confidence": 0.8,
            "checksum_valid": None,
            "recognizer": "email_regex",
            "method": "full_mask",
            "placeholder": None,
            "in_review": False,
        }
    )
    assert f.start == 1 and f.end == 5
    assert f.recognizer == "email_regex"
    assert f.method == "full_mask"


def test_finding_keeps_unknown_fields_in_raw() -> None:
    f = Finding.from_api(
        {"category": "email", "start": 0, "end": 1, "confidence": 0.5, "future_field": "x"}
    )
    assert f.raw["future_field"] == "x"


def test_scan_result_defaults_to_empty_findings() -> None:
    result = ScanResult.from_api({})
    assert result.findings == []


def test_protection_result_reads_protected_and_scope_id() -> None:
    result = ProtectionResult.from_api(
        {"protected": "[REDACTED]", "findings": [], "scope_id": "s1"}
    )
    assert not hasattr(result, "value")
    assert not hasattr(result, "original")
    assert result.protected_text == "[REDACTED]"
    assert result.scope_id == "s1"


def test_protect_result_reads_protected_prompt_and_scope_id() -> None:
    result = ProtectResult.from_api(
        {"protected_prompt": "safe to send", "scope_id": "tm_1", "findings": []}
    )
    assert result.protected_text == "safe to send"
    assert result.scope_id == "tm_1"
    # protected_text and scope_id are different attributes; nothing merges them.
    assert result.protected_text != result.scope_id
