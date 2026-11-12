"""Unit tests for the validated checksums (AC2's correctness core)."""

from __future__ import annotations

from piishield.detectors.checksums import (
    iban_ok,
    ifsc_ok,
    luhn_ok,
    pan_entity_ok,
    us_ssn_ok,
    verhoeff_ok,
)


def test_luhn_ok_valid_card() -> None:
    assert luhn_ok("4539148803436467") is True


def test_luhn_ok_invalid_card() -> None:
    assert luhn_ok("4539148803436468") is False


def test_luhn_ok_random_digits_usually_invalid() -> None:
    # A fixed random-looking 16-digit string with no relation to a real card: it must not
    # pass the Luhn check (this is the exact property AC2 requires).
    assert luhn_ok("1234567890123456") is False


def test_verhoeff_ok_valid_aadhaar() -> None:
    # A Verhoeff-valid 12-digit string (computed check digit appended to a base number).
    assert verhoeff_ok("234123412346") is True


def test_verhoeff_ok_invalid_aadhaar() -> None:
    assert verhoeff_ok("234123412345") is False


def test_iban_ok_valid() -> None:
    assert iban_ok("GB82 WEST 1234 5698 7654 32") is True


def test_iban_ok_invalid_checksum() -> None:
    assert iban_ok("GB82 WEST 1234 5698 7654 33") is False


def test_iban_ok_too_short() -> None:
    assert iban_ok("GB82WEST") is False


def test_us_ssn_ok_valid_shape() -> None:
    assert us_ssn_ok("123", "45", "6789") is True


def test_us_ssn_ok_rejects_all_zero_area() -> None:
    assert us_ssn_ok("000", "45", "6789") is False


def test_us_ssn_ok_rejects_666_area() -> None:
    assert us_ssn_ok("666", "45", "6789") is False


def test_us_ssn_ok_rejects_9_prefixed_area() -> None:
    assert us_ssn_ok("912", "45", "6789") is False


def test_us_ssn_ok_rejects_zero_group() -> None:
    assert us_ssn_ok("123", "00", "6789") is False


def test_us_ssn_ok_rejects_zero_serial() -> None:
    assert us_ssn_ok("123", "45", "0000") is False


def test_pan_entity_ok_person() -> None:
    assert pan_entity_ok("P") is True


def test_pan_entity_ok_invalid_letter() -> None:
    assert pan_entity_ok("Z") is False


def test_ifsc_ok_valid() -> None:
    assert ifsc_ok("HDFC0001234") is True


def test_ifsc_ok_missing_reserved_zero() -> None:
    assert ifsc_ok("HDFC1001234") is False
