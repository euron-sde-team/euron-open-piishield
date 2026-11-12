"""The four protection methods (AC3). Pure string transforms; no I/O, no database.

* ``full_mask``: the whole matched span becomes a fixed-length mask, so the output gives
  no hint of the original length.
* ``partial_mask``: keeps the last ``reveal`` characters of the matched text, masks the
  rest. ``reveal`` is configurable per policy (``partial_mask_reveal``).
* ``redact``: the span is replaced by ``[REDACTED:<category>]``. Nothing about the
  original value (length, characters, a hash) survives in the output (AC3's "no way to
  recover the original from the response alone").
* ``tokenize``: the span is replaced by a stable placeholder from ``vault.service``; this
  module only applies the already-computed placeholder string, it never talks to the
  vault itself (that would entangle a pure string transform with async I/O and secrets).
"""

from __future__ import annotations

FULL_MASK = "****"


def full_mask(_matched_text: str) -> str:
    return FULL_MASK


def partial_mask(matched_text: str, reveal: int) -> str:
    if reveal <= 0:
        return "*" * len(matched_text)
    if reveal >= len(matched_text):
        return matched_text
    hidden = len(matched_text) - reveal
    return "*" * hidden + matched_text[-reveal:]


def redact(category: str) -> str:
    return f"[REDACTED:{category}]"


def apply_replacement(text: str, start: int, end: int, replacement: str) -> str:
    return text[:start] + replacement + text[end:]


def apply_many(text: str, replacements: list[tuple[int, int, str]]) -> str:
    """Apply several (start, end, replacement) spans to one string, highest offset
    first, so earlier offsets stay valid as later ones are substituted."""
    out = text
    for start, end, replacement in sorted(replacements, key=lambda r: r[0], reverse=True):
        out = apply_replacement(out, start, end, replacement)
    return out
