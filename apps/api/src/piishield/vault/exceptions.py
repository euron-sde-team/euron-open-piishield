"""Vault domain errors. None of these ever carry a value in their message or details."""

from __future__ import annotations

from piishield.core.errors import NotFoundError


class PlaceholderNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__(
            "No vault entry for this placeholder in this scope", code="placeholder_not_found"
        )
