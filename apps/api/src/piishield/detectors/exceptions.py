"""Detector domain errors."""

from __future__ import annotations

from piishield.core.errors import AppError, NotFoundError


class InvalidPatternError(AppError):
    status_code = 422
    code = "invalid_pattern"

    def __init__(self, pattern: str, reason: str) -> None:
        super().__init__(
            f"The custom pattern could not be compiled: {reason}",
            code="invalid_pattern",
            details={"pattern": pattern},
        )


class RecognizerNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("Custom recognizer not found")
