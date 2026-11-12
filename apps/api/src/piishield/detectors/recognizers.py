"""Recognizers: regex patterns plus checksum validation, each producing a :class:`Finding`.

AC2: every finding carries ``category``, the exact ``start``/``end`` character offset into
the original text, a ``confidence`` score, and, where a checksum applies, whether it
passed. A value whose checksum fails is never reported as that category at all (not
reported with low confidence: not reported), which is what makes a random 16-digit string
provably not a card number (see ``tests/unit/test_detectors.py::test_ac2_card_checksum``).

Overlap resolution: recognizers are tried in a fixed order (most specific/highest-signal
first); once a span is claimed, no later, lower-priority recognizer may claim a span that
overlaps it. This stops a card number also being reported as a generic phone-like digit
run, and a password-assignment line also being reported as a bare API key.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from re import Match

from piishield.detectors.checksums import (
    iban_ok,
    ifsc_ok,
    luhn_ok,
    pan_entity_ok,
    us_ssn_ok,
    verhoeff_ok,
)

MAX_SCAN_CHARS = 2_000_000


@dataclass(frozen=True, slots=True)
class Finding:
    category: str
    start: int
    end: int
    confidence: float
    matched_text: str = field(repr=False)
    checksum_valid: bool | None = None
    recognizer: str = ""

    def as_dict(self) -> dict[str, object]:
        """Never includes ``matched_text``: callers that build a response from findings
        use this, not the dataclass itself, so the original value cannot leak by accident
        (see protection.service, which is the only place matched_text is read)."""
        return {
            "category": self.category,
            "start": self.start,
            "end": self.end,
            "confidence": self.confidence,
            "checksum_valid": self.checksum_valid,
            "recognizer": self.recognizer,
        }


Validator = Callable[[Match[str]], tuple[bool, bool | None]]


@dataclass(frozen=True, slots=True)
class Recognizer:
    name: str
    category: str
    pattern: re.Pattern[str]
    confidence: float
    # Returns (ok, checksum_valid | None). ok False means "do not report this match at
    # all" (the checksum proved it cannot be this category). checksum_valid is reported
    # verbatim in the Finding when the category has a checksum concept.
    validate: Validator | None = None

    def check(self, m: Match[str]) -> tuple[bool, bool | None]:
        if self.validate is None:
            return True, None
        return self.validate(m)


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def _card_validate(m: Match[str]) -> tuple[bool, bool | None]:
    digits = _digits(m.group(0))
    if not 13 <= len(digits) <= 19:
        return False, None
    ok = luhn_ok(digits)
    return ok, ok


def _iban_validate(m: Match[str]) -> tuple[bool, bool | None]:
    ok = iban_ok(m.group(0))
    return ok, ok


def _aadhaar_validate(m: Match[str]) -> tuple[bool, bool | None]:
    digits = _digits(m.group(0))
    if len(digits) != 12:
        return False, None
    ok = verhoeff_ok(digits)
    return ok, ok


def _ssn_validate(m: Match[str]) -> tuple[bool, bool | None]:
    ok = us_ssn_ok(m.group(1), m.group(2), m.group(3))
    return ok, ok


def _pan_validate(m: Match[str]) -> tuple[bool, bool | None]:
    ok = pan_entity_ok(m.group(0)[3])
    return ok, ok


def _ifsc_validate(m: Match[str]) -> tuple[bool, bool | None]:
    ok = ifsc_ok(m.group(0))
    return ok, ok


def _phone_validate(m: Match[str]) -> tuple[bool, None]:
    digits = _digits(m.group(0))
    return 8 <= len(digits) <= 15, None


def _dob_validate(m: Match[str]) -> tuple[bool, None]:
    try:
        day, month, year = _dob_parts(m)
    except ValueError:
        return False, None
    return (1 <= month <= 12 and 1 <= day <= 31 and 1900 <= year <= 2026), None


def _dob_parts(m: Match[str]) -> tuple[int, int, int]:
    a, b, c = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if len(m.group(3)) == 4:  # DD-MM-YYYY or MM-DD-YYYY (day/month resolved loosely)
        day, month, year = a, b, c
        if month > 12:
            day, month = month, day
        return day, month, year
    # YYYY-MM-DD
    return c, b, a


# Credentials: API key / JWT / password-assignment patterns.
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
_GENERIC_API_KEY = re.compile(
    r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"
    r"|\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}\b"
    r"|\bgh[pousr]_[A-Za-z0-9]{36,}\b"
    r"|\bAIza[0-9A-Za-z_-]{35}\b"
)
_PASSWORD_ASSIGNMENT = re.compile(
    r"(?i)\b(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token)\b\s*[:=]\s*['\"]?([^\s'\"]{6,})"
)

# Core recognizer table, highest priority first. Order matters for overlap resolution.
RECOGNIZERS: list[Recognizer] = [
    Recognizer("jwt", "credential", _JWT, 0.95),
    Recognizer("api_key", "credential", _GENERIC_API_KEY, 0.9),
    Recognizer("password_assignment", "credential", _PASSWORD_ASSIGNMENT, 0.85),
    Recognizer(
        "credit_card",
        "financial",
        re.compile(r"(?<![\d-])(?:\d[ -]?){12,18}\d(?![\d-])"),
        0.95,
        _card_validate,
    ),
    Recognizer(
        "iban",
        "financial",
        re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,4})?\b"),
        0.9,
        _iban_validate,
    ),
    Recognizer(
        "swift_bic",
        "financial",
        re.compile(r"\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b"),
        0.55,
    ),
    Recognizer("ifsc", "financial", re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"), 0.85, _ifsc_validate),
    # Email is tried before upi_id: a UPI handle has no dot in its bank suffix (@paytm,
    # @ybl, @okaxis), unlike an email's multi-label domain (@example.com), so putting email
    # first and excluding dots from upi_id's suffix keeps the two from overlap-colliding.
    Recognizer(
        "email",
        "contact",
        re.compile(r"\b[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,253}\.[A-Za-z]{2,24}\b"),
        0.95,
    ),
    Recognizer(
        "upi_id",
        "financial",
        re.compile(r"\b[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z]{2,64}\b(?!\.[A-Za-z])"),
        0.6,
    ),
    Recognizer(
        "aadhaar",
        "government_id",
        re.compile(r"(?<!\d)[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}(?!\d)"),
        0.95,
        _aadhaar_validate,
    ),
    Recognizer(
        "pan",
        "government_id",
        re.compile(r"\b[A-Z]{3}[A-Z]{1}[A-Z]\d{4}[A-Z]\b"),
        0.9,
        _pan_validate,
    ),
    Recognizer(
        "us_ssn",
        "government_id",
        re.compile(r"\b(\d{3})-(\d{2})-(\d{4})\b"),
        0.9,
        _ssn_validate,
    ),
    Recognizer(
        "passport",
        "government_id",
        re.compile(r"\b[A-Z]{1}[0-9]{7}\b"),
        0.5,
    ),
    Recognizer(
        "driving_licence",
        "government_id",
        re.compile(r"\b[A-Z]{2}[0-9]{2}[ ]?[0-9]{11}\b"),
        0.55,
    ),
    Recognizer(
        "phone_in",
        "contact",
        re.compile(r"(?<![\d+])(?:\+91[ -]?)?[6-9]\d{4}[ -]?\d{5}(?!\d)"),
        0.8,
        _phone_validate,
    ),
    Recognizer(
        "phone_us",
        "contact",
        re.compile(r"(?<![\w+])(?:\+1[ .-]?)?\(?\d{3}\)?[ .-]?\d{3}[ .-]?\d{4}(?!\d)"),
        0.75,
        _phone_validate,
    ),
    # bank_account is a pure digit-count match with no checksum (the brief's own PLAN.md
    # calls it "pattern-assisted" only), so it is deliberately tried LAST among the
    # digit-shaped recognizers: every more specific, higher-confidence, checksum- or
    # format-validated recognizer above (aadhaar, pan, us_ssn, passport, driving_licence,
    # phone_in, phone_us) gets first chance to claim an overlapping span. Declaring this
    # earlier would let it steal a valid Aadhaar/SSN/phone number's span before the
    # correct, validated recognizer ever sees it (overlap resolution is first-claim-wins
    # by list order; see scan_text's docstring above).
    Recognizer(
        "bank_account",
        "financial",
        re.compile(r"(?<!\d)\d{9,18}(?!\d)"),
        0.3,
    ),
    Recognizer(
        "date_of_birth",
        "personal",
        re.compile(r"\b(\d{1,4})[/-](\d{1,2})[/-](\d{1,4})\b"),
        0.4,
        _dob_validate,
    ),
    Recognizer(
        "address",
        "personal",
        re.compile(
            r"\b\d{1,5}\s+[A-Za-z0-9.\s]{3,40}\s(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Nagar|Colony|Marg)\b[,]?\s*[A-Za-z\s]{2,40}[,]?\s*\d{5,6}\b"
        ),
        0.55,
    ),
    Recognizer(
        "person_name",
        "personal",
        re.compile(r"\b(?:Mr|Mrs|Ms|Dr|Mx)\.?\s[A-Z][a-z]+(?:\s[A-Z][a-z]+){0,2}\b"),
        0.5,
    ),
]


def custom_recognizer(
    name: str, category: str, pattern: str, confidence: float = 0.7
) -> Recognizer:
    """A per-project custom pattern (PLAN.md's "custom-pattern recognizer per project").
    Compiled once by the caller and cached; invalid patterns raise re.error, caught by the
    service layer at the API boundary (a 422, never a 500)."""
    return Recognizer(name, category, re.compile(pattern), confidence)


def scan_text(
    text: str, recognizers: list[Recognizer] | None = None, max_chars: int = MAX_SCAN_CHARS
) -> list[Finding]:
    """Every finding in ``text``, with overlapping lower-priority matches suppressed."""
    text = text[:max_chars]
    active = recognizers if recognizers is not None else RECOGNIZERS
    findings: list[Finding] = []
    taken: list[tuple[int, int]] = []
    for rec in active:
        for m in rec.pattern.finditer(text):
            span = (m.start(), m.end())
            if span[0] == span[1]:
                continue
            if any(s < span[1] and span[0] < e for s, e in taken):
                continue  # a higher-priority recognizer already claimed this text
            ok, checksum_valid = rec.check(m)
            if not ok:
                continue
            taken.append(span)
            findings.append(
                Finding(
                    category=rec.category,
                    start=span[0],
                    end=span[1],
                    confidence=rec.confidence,
                    matched_text=m.group(0),
                    checksum_valid=checksum_valid,
                    recognizer=rec.name,
                )
            )
    findings.sort(key=lambda f: f.start)
    return findings
