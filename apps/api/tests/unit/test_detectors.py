"""Unit tests for the recognizer table (AC2): category, exact span, confidence, and
checksum validity for every recognizer family, plus the single most important
correctness property: a checksum-invalid value is never reported as that category at
all, not reported with low confidence (``test_ac2_card_checksum_invalid_not_reported``
and friends below)."""

from __future__ import annotations

from piishield.detectors.recognizers import scan_text


def _only(text: str, category: str) -> list[object]:
    return [f for f in scan_text(text) if f.category == category]


def test_ac2_email_span_and_confidence() -> None:
    text = "contact us at ops@example.com for help"
    findings = scan_text(text)
    hit = next(f for f in findings if f.recognizer == "email")
    assert text[hit.start : hit.end] == "ops@example.com"
    assert hit.category == "contact"
    assert hit.confidence > 0.9
    assert hit.checksum_valid is None


def test_ac2_card_checksum_valid_is_reported_with_result_true() -> None:
    findings = scan_text("card on file: 4539148803436467")
    hit = next(f for f in findings if f.recognizer == "credit_card")
    assert hit.checksum_valid is True
    assert hit.category == "financial"


def test_ac2_card_checksum_invalid_not_reported() -> None:
    """The single most important correctness property: a random 16-digit string that
    fails Luhn must never be reported as a credit_card finding at all."""
    findings = scan_text("reference number: 1234567890123456")
    assert not any(f.recognizer == "credit_card" for f in findings)


def test_ac2_aadhaar_checksum_valid() -> None:
    findings = scan_text("Aadhaar: 2341 2341 2346")
    hit = next(f for f in findings if f.recognizer == "aadhaar")
    assert hit.checksum_valid is True
    assert hit.category == "government_id"


def test_ac2_aadhaar_checksum_invalid_not_reported() -> None:
    findings = scan_text("Aadhaar-looking number: 2341 2341 2345")
    assert not any(f.recognizer == "aadhaar" for f in findings)


def test_ac2_iban_checksum_valid() -> None:
    findings = scan_text("IBAN GB82WEST12345698765432 on file")
    hit = next(f for f in findings if f.recognizer == "iban")
    assert hit.checksum_valid is True


def test_ac2_iban_checksum_invalid_not_reported() -> None:
    findings = scan_text("IBAN-looking value GB82WEST12345698765433 on file")
    assert not any(f.recognizer == "iban" for f in findings)


def test_ac2_pan_entity_rule_valid() -> None:
    findings = scan_text("PAN: ABCPD1234E")
    hit = next(f for f in findings if f.recognizer == "pan")
    assert hit.checksum_valid is True
    assert hit.category == "government_id"


def test_ac2_pan_entity_rule_invalid_not_reported() -> None:
    # The 4th character ("Z") is not a valid PAN entity-type character.
    findings = scan_text("Reference: ABCZD1234E")
    assert not any(f.recognizer == "pan" for f in findings)


def test_ac2_us_ssn_valid_shape() -> None:
    findings = scan_text("SSN 123-45-6789 on file")
    hit = next(f for f in findings if f.recognizer == "us_ssn")
    assert hit.checksum_valid is True
    assert hit.category == "government_id"


def test_ac2_us_ssn_invalid_area_not_reported() -> None:
    findings = scan_text("SSN-looking value 000-45-6789 on file")
    assert not any(f.recognizer == "us_ssn" for f in findings)


def test_ac2_ifsc_valid() -> None:
    findings = scan_text("IFSC: HDFC0001234")
    hit = next(f for f in findings if f.recognizer == "ifsc")
    assert hit.checksum_valid is True
    assert hit.category == "financial"


def test_ac2_ifsc_invalid_not_reported() -> None:
    findings = scan_text("Code: HDFC1001234")
    assert not any(f.recognizer == "ifsc" for f in findings)


def test_ac2_jwt_detected_as_credential() -> None:
    token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    findings = scan_text(f"Authorization: Bearer {token}")
    assert any(f.recognizer == "jwt" and f.category == "credential" for f in findings)


def test_ac2_password_assignment_detected() -> None:
    findings = scan_text("password: Sup3rSecretValue1")
    assert any(f.recognizer == "password_assignment" for f in findings)


def test_ac2_date_of_birth_plausible_date_accepted() -> None:
    findings = scan_text("DOB: 1990-05-21")
    assert any(f.recognizer == "date_of_birth" for f in findings)


def test_ac2_date_of_birth_implausible_date_rejected() -> None:
    findings = scan_text("Ratio: 1990-99-99")
    assert not any(f.recognizer == "date_of_birth" for f in findings)


def test_ac2_phone_in_detected() -> None:
    findings = scan_text("call me at +91 98765 43210")
    assert any(f.recognizer == "phone_in" and f.category == "contact" for f in findings)


def test_ac2_custom_pattern_recognizer() -> None:
    from piishield.detectors.recognizers import custom_recognizer
    from piishield.detectors.recognizers import scan_text as scan

    rec = custom_recognizer("ticket_id", "custom", r"\bTCK-\d{6}\b", confidence=0.8)
    findings = scan("see ticket TCK-123456 for details", [rec])
    assert findings[0].category == "custom"
    assert findings[0].recognizer == "ticket_id"


def test_overlap_resolution_higher_priority_wins() -> None:
    """A valid card number must not ALSO be reported by a lower-priority generic digit
    recognizer (bank_account) overlapping the same span."""
    findings = scan_text("4539148803436467")
    spans = [(f.start, f.end) for f in findings]
    assert len(spans) == len(set(spans))  # no two findings share an identical span
