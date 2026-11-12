"""Protection domain errors."""

from __future__ import annotations

from piishield.core.errors import PolicyRefusedError


class RequiredCategoryUnmaskedError(PolicyRefusedError):
    """AC10: a required category was requested with masking effectively disabled
    (skip_categories, or a method_override that is not a real masking method). The raw
    value is never passed through; the caller must drop the skip/override or accept the
    policy default."""

    def __init__(self, category: str) -> None:
        super().__init__(
            f"'{category}' is a required category under this project's policy and cannot be left unmasked",
            code="required_category_unmasked",
            details={"category": category},
        )
