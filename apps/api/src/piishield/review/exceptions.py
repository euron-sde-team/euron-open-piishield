"""Review domain errors."""

from __future__ import annotations

from piishield.core.errors import ConflictError, NotFoundError


class ReviewItemNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("Review item not found")


class ReviewItemAlreadyDecidedError(ConflictError):
    def __init__(self) -> None:
        super().__init__("This review item was already decided", code="already_decided")
