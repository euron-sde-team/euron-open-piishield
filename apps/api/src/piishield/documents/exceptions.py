"""Document domain errors."""

from __future__ import annotations

from piishield.core.errors import AppError


class UnsupportedDocumentTypeError(AppError):
    status_code = 422
    code = "unsupported_document_type"

    def __init__(self, filename: str) -> None:
        super().__init__(
            f"'{filename}' is not a supported document type (pdf, docx, xlsx, csv)",
            code="unsupported_document_type",
            details={"filename": filename},
        )


class DocumentParseError(AppError):
    status_code = 422
    code = "document_parse_error"

    def __init__(self, reason: str) -> None:
        super().__init__(f"The document could not be read: {reason}", code="document_parse_error")
