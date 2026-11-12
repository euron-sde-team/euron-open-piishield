"""Policy domain errors."""

from __future__ import annotations

from piishield.core.errors import NotFoundError


class PolicyNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("Policy not found")
