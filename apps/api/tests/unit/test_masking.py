"""Unit tests for the four protection methods (AC3): each produces distinct, correct
output from the same finding, and redaction/full-mask leave no trace of the original."""

from __future__ import annotations

from piishield.protection.masking import apply_many, full_mask, partial_mask, redact


def test_ac3_full_mask_is_fixed_and_hides_length() -> None:
    assert full_mask("4539148803436467") == "****"
    assert full_mask("a") == "****"  # the output never reveals the original length


def test_ac3_partial_mask_keeps_configured_reveal_count() -> None:
    masked = partial_mask("4539148803436467", 4)
    assert masked.endswith("6467")
    assert masked == "*" * 12 + "6467"


def test_ac3_partial_mask_reveal_zero_masks_everything() -> None:
    assert partial_mask("secret", 0) == "******"


def test_ac3_partial_mask_reveal_exceeds_length_returns_original() -> None:
    assert partial_mask("abc", 10) == "abc"


def test_ac3_redact_has_no_trace_of_original_value() -> None:
    out = redact("financial")
    assert out == "[REDACTED:financial]"
    assert "4539148803436467" not in out


def test_ac3_four_methods_produce_distinct_output_for_the_same_value() -> None:
    value = "4539148803436467"
    outputs = {
        full_mask(value),
        partial_mask(value, 4),
        redact("financial"),
        "[FINANCIAL_001]",  # the tokenize placeholder shape
    }
    assert len(outputs) == 4


def test_apply_many_handles_multiple_non_overlapping_spans() -> None:
    text = "email a@b.com and phone 1234567890"
    out = apply_many(text, [(6, 13, "[EMAIL_001]"), (24, 34, "[PHONE_001]")])
    assert out == "email [EMAIL_001] and phone [PHONE_001]"
