"""Validated checksums used by the recognizers in ``recognizers.py``.

A regex alone over-matches: a random 16-digit string is not a valid card number, and a
random 12-digit string is not a valid Aadhaar number. Every function here is a pure
mathematical check with no knowledge of formatting; callers strip non-digit characters
before calling. These are the single most important functions in this module: AC2's core
correctness property (a checksum-invalid value is never reported as that category) rests
entirely on them being right.
"""

from __future__ import annotations


def luhn_ok(digits: str) -> bool:
    """The Luhn (mod 10) checksum used by credit/debit card numbers and some bank ids."""
    if not digits.isdigit():
        return False
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = ord(ch) - 48
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


_VERHOEFF_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_VERHOEFF_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)


def verhoeff_ok(digits: str) -> bool:
    """The Verhoeff checksum used by Indian Aadhaar numbers (the last of 12 digits)."""
    if not digits.isdigit():
        return False
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][ord(ch) - 48]]
    return c == 0


def iban_ok(raw: str) -> bool:
    """ISO 7064 MOD 97-10, as specified for IBAN: move the first 4 chars to the end, map
    each letter to two digits (A=10 .. Z=35), and the resulting number mod 97 must be 1."""
    iban = raw.replace(" ", "").upper()
    if not 15 <= len(iban) <= 34:
        return False
    if not iban[:2].isalpha() or not iban[2:4].isdigit():
        return False
    moved = iban[4:] + iban[:4]
    try:
        number = int("".join(str(int(c, 36)) for c in moved))
    except ValueError:
        return False
    return number % 97 == 1


def us_ssn_ok(area: str, group: str, serial: str) -> bool:
    """Area/group/serial sanity rules the SSA never issues (not a full validity proof:
    SSNs have no mathematical checksum, only a well-formedness check)."""
    return not (area in ("000", "666") or area.startswith("9") or group == "00" or serial == "0000")


_PAN_ENTITY_CHARS = set("PCHFATBLJG")


def pan_entity_ok(fourth_char: str) -> bool:
    """The 4th character of a PAN encodes the holder's entity type (P person, C company,
    H HUF, F firm, A AOP, T trust, B body of individuals, L local authority, J artificial
    judicial person, G government); anything else is not a PAN."""
    return fourth_char.upper() in _PAN_ENTITY_CHARS


def ifsc_ok(code: str) -> bool:
    """IFSC structure: 4 letters (bank code), then a literal 0 (reserved), then 6
    alphanumeric branch chars. No public checksum digit exists; this is a format check."""
    code = code.upper()
    return len(code) == 11 and code[:4].isalpha() and code[4] == "0" and code[5:].isalnum()
