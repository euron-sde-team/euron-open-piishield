"""What the sync and async clients share: option checks, request bodies and error mapping.

No I/O happens here. See the README's "Wire format" section for the full request and
response shapes this module encodes and decodes, matching ``apps/api/src/piishield``'s
real routers and schemas.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import httpx

from euron_piishield._version import __version__
from euron_piishield.errors import (
    APIError,
    PolicyViolationError,
    UnsupportedFileTypeError,
    VaultPermissionError,
)

USER_AGENT = f"euron-piishield-python/{__version__}"

# Maps a file extension to the content type sent to /api/v1/documents.
CONTENT_TYPE_BY_EXTENSION = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".csv": "text/csv",
}


def check_options(api_url: str, api_key: str) -> str:
    if not api_url.startswith(("http://", "https://")):
        raise ValueError("api_url must be an http(s) URL, for example http://localhost:5530")
    if not api_key:
        raise ValueError("api_key is required (create one under a project's API keys)")
    return api_url.rstrip("/")


def guess_content_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    try:
        return CONTENT_TYPE_BY_EXTENSION[suffix]
    except KeyError:
        supported = ", ".join(sorted(CONTENT_TYPE_BY_EXTENSION))
        raise UnsupportedFileTypeError(
            f"Cannot tell the content type for {filename!r}: pass filename= explicitly, "
            f"or use one of the supported extensions ({supported})"
        ) from None


def protect_text_body(
    project_id: str,
    text: str,
    method_overrides: dict[str, str] | None,
    skip_categories: list[str] | None,
    scope_id: str | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"project_id": project_id, "text": text}
    if method_overrides:
        body["method_overrides"] = dict(method_overrides)
    if skip_categories:
        body["skip_categories"] = list(skip_categories)
    if scope_id is not None:
        body["scope_id"] = scope_id
    return body


def protect_json_body(
    project_id: str,
    payload: Any,
    method_overrides: dict[str, str] | None,
    skip_categories: list[str] | None,
    scope_id: str | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"project_id": project_id, "payload": payload}
    if method_overrides:
        body["method_overrides"] = dict(method_overrides)
    if skip_categories:
        body["skip_categories"] = list(skip_categories)
    if scope_id is not None:
        body["scope_id"] = scope_id
    return body


def error_from(response: httpx.Response, *, context: str) -> APIError:
    """The typed error for a non-2xx response.

    The real error body is ``{"error": {"code", "type", "message", "details"}}``
    (``piishield.core.errors.AppError.body``). ``context`` names the call being made
    ("detokenize", "protect", ...), but the mapping to a specific subclass is driven by
    the server's own ``code``, which is stable across every endpoint that can produce it:
    a 403 with code ``vault_access_required`` is always :class:`VaultPermissionError`
    (AC5), and a 422 with code ``required_category_unmasked`` is always
    :class:`PolicyViolationError` (AC10), wherever it happens.
    """
    try:
        body: Any = response.json()
    except ValueError:
        body = {}
    err = body.get("error") if isinstance(body, dict) else None
    if isinstance(err, dict):
        code = str(err.get("code") or "api_error")
        message = str(err.get("message") or response.reason_phrase or "error")
        details = err.get("details") if isinstance(err.get("details"), dict) else {}
    else:
        code, message, details = "api_error", response.reason_phrase or "error", {}

    if response.status_code == 403 and code == "vault_access_required":
        return VaultPermissionError(
            message, status_code=response.status_code, code=code, details=details
        )
    if response.status_code == 422 and code == "required_category_unmasked":
        return PolicyViolationError(
            message, status_code=response.status_code, code=code, details=details
        )
    return APIError(message, status_code=response.status_code, code=code, details=details)


def env_integration_config(prefix: str) -> tuple[str, str, str] | None:
    """``(api_url, api_key, project_id)`` from ``{PREFIX}_API_URL``/``{PREFIX}_API_KEY``/
    ``{PREFIX}_PROJECT_ID``, or None.

    Integration tests skip gracefully when these are unset, matching the sibling
    projects' pattern (see ``tests/integration``).
    """
    url = os.environ.get(f"{prefix}_API_URL", "")
    key = os.environ.get(f"{prefix}_API_KEY", "")
    project_id = os.environ.get(f"{prefix}_PROJECT_ID", "")
    if not url or not key or not project_id:
        return None
    return url, key, project_id


def read_file_bytes(path_or_bytes: str | bytes | Path, filename: str | None) -> tuple[bytes, str]:
    if isinstance(path_or_bytes, bytes):
        if not filename:
            raise ValueError("filename is required when passing raw bytes")
        return path_or_bytes, filename
    path = Path(path_or_bytes)
    return path.read_bytes(), filename or path.name


def ensure_mapping(value: Any, *, what: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{what} must be a JSON object (dict), got {type(value).__name__}")
    return value
