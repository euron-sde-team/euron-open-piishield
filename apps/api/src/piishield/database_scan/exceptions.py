"""Database scan domain errors."""

from __future__ import annotations

from piishield.core.errors import AppError


class DatabaseConnectionError(AppError):
    status_code = 422
    code = "database_connection_failed"

    def __init__(self) -> None:
        # Deliberately no driver-reported detail: it can echo back parts of the
        # connection string (host, user) that the caller may not want logged or returned.
        super().__init__(
            "Could not connect to the database with the given connection string",
            code="database_connection_failed",
        )
