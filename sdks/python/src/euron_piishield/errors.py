"""Exceptions the SDK raises.

Every call that reaches the API either returns a typed result or raises one of these.
Catch :class:`PIIShieldError` for "something went wrong talking to PIIShield", or catch a
specific subclass when the caller needs to react differently (for example, show a
permission-request flow on :class:`VaultPermissionError` instead of a generic failure page).
"""

from __future__ import annotations

from typing import Any


class PIIShieldError(Exception):
    """Base class of every exception this SDK raises."""


class APIError(PIIShieldError):
    """PIIShield answered with an error response: ``{"error": {"code", "type", "message",
    "details"}}`` (``piishield.core.errors.AppError.body``).

    Raised for any non-2xx response that is not one of the more specific cases below
    (:class:`VaultPermissionError` for a 403 with code ``vault_access_required``,
    :class:`PolicyViolationError` for a 422 with code ``required_category_unmasked``).
    Network failures and timeouts raise :class:`ConnectionError` (from this module, not
    the builtin), never this class.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str = "api_error",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details or {}

    def __repr__(self) -> str:
        return f"{type(self).__name__}(status_code={self.status_code!r}, code={self.code!r})"


class ConnectionError(PIIShieldError):
    """PIIShield could not be reached at all (connection refused, DNS failure, timeout).

    Distinct from :class:`APIError`: the request never got a response to interpret, so
    there is no status code, no error code and no details from the server. Also raised
    (by the SDK, from the server's own 503) when a dependency PIIShield needs (Postgres,
    Redis, the mock AI service) is down: the server's contract is to answer with a clear,
    retryable 503 rather than a response that silently omits findings, so the SDK surfaces
    that as a connection-shaped failure too (its ``retry-after`` header is in ``details``
    on the underlying :class:`APIError` this wraps, where available).
    """


class VaultPermissionError(APIError):
    """``detokenize`` was refused because the caller lacks the vault-access grant.

    This is a 403 with error code ``vault_access_required`` (AC5 of PLAN.md): a caller
    without a vault grant (``POST /api/v1/vault/grants``, owner only) gets this exception,
    never the original value and never a hint of it in ``message`` or ``details``. The
    base API key used for every other call does not, by itself, grant this. See the
    README's "Vault permission model" section.
    """


class PolicyViolationError(APIError):
    """A ``protect`` or ``mask`` call was refused by policy, never silently downgraded.

    Raised when the project's policy marks a detected category as required to be masked
    (``policy.required_categories``) and the call's ``skip_categories`` or
    ``method_overrides`` would have left it unmasked (AC10 of PLAN.md; the server's error
    code is ``required_category_unmasked``, status 422). PIIShield refuses the whole call
    rather than silently returning the raw value for that category.
    """


class UnsupportedFileTypeError(PIIShieldError):
    """``scan_file``/``protect_file`` was given a file type PIIShield does not know how to
    scan (only PDF, DOCX, XLSX and CSV are supported).

    Raised client side before any request is sent, from an unrecognised extension when a
    path is passed without an explicit ``filename``.
    """
