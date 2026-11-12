"""The synchronous client: ``PIIShield``.

See the package README for the full wire format and a worked example of every call. This
client targets the real routers in ``apps/api/src/piishield`` (``protection``, ``vault``,
``ai_gateway``, ``documents``, ``database_scan``, ``policies``, ``audit``, ``review``),
not the product brief's own illustrative endpoint names: see the README's "Wire format"
section for the mapping.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from euron_piishield import _core
from euron_piishield.errors import ConnectionError as PIIShieldConnectionError
from euron_piishield.models import (
    AuditLogPage,
    DatabaseScanResult,
    DetokenizeResult,
    Policy,
    ProtectionJsonResult,
    ProtectionResult,
    ProtectResult,
    RestoreResult,
    ReviewItem,
    ScanResult,
)

# Every category a fresh install's detectors can report. Used by scan() to request every
# category be skipped (left unmasked), so a scan never actually protects anything, only
# detects: the real API has no separate bare scan endpoint (see the README's "Wire
# format" section, point 1). A project with a required category still gets that category
# protected regardless (AC10: skip is refused for a required category), so scan() on
# text containing a required category will find that one already protected; its
# `in_review`/`method` fields on that finding still tell the caller what happened.
ALL_CATEGORIES = [
    "contact",
    "credential",
    "financial",
    "government_id",
    "personal",
]
"""The real server-side categories (matches every ``Recognizer.category`` in
``piishield.detectors.recognizers.RECOGNIZERS``), used as ``method_overrides``/
``skip_categories`` keys. An earlier version of this list used per-recognizer names
(``"email"``, ``"pan"``, ``"credit_card"``, ...), which never matched any finding's real
``category`` server side (``protection.service._effective_method`` looks up
``overrides.get(category, ...)`` against the coarse category, not the recognizer name),
so every ``mask``/``tokenize``/``redact``/``anonymize`` call silently fell through to the
project's own policy default for that category instead of applying the method the caller
asked for. Confirmed live: ``tokenize("rahul@example.com")`` against the demo project
(policy: contact -> partial_mask) returned a partial mask, never a placeholder, until this
was fixed."""


class PIIShield:
    """A connection to a self-hosted PIIShield API, scoped to one project.

    ::

        shield = PIIShield(
            api_url="http://localhost:8000", api_key="YOUR_API_KEY", project_id="..."
        )
        result = shield.mask("Customer: Rahul Sharma\\nEmail: rahul@example.com")
        print(result.protected_text)

    Every method is a blocking HTTP call (the brief's example usage is synchronous). For
    asyncio code, use :class:`~euron_piishield.AsyncPIIShield`, which exposes the exact
    same methods, awaited.

    Thread safe: one instance can be shared by every thread of a process.
    """

    def __init__(
        self,
        api_url: str,
        api_key: str,
        project_id: str,
        *,
        timeout: float = 30.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_url = _core.check_options(api_url, api_key)
        self.api_key = api_key
        self.project_id = project_id
        self.timeout = timeout
        self._own_http = http_client is None
        self._http = http_client or httpx.Client(timeout=timeout)

    def close(self) -> None:
        if self._own_http:
            self._http.close()

    def __enter__(self) -> PIIShield:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # Transport

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "User-Agent": _core.USER_AGENT}

    def _request(
        self,
        method: str,
        path: str,
        body: Any = None,
        *,
        context: str = "",
        params: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        raw: bool = False,
    ) -> Any:
        headers = self._headers()
        try:
            if files is not None:
                response = self._http.request(
                    method,
                    f"{self.api_url}{path}",
                    headers=headers,
                    params=params,
                    files=files,
                    data=body,
                )
            else:
                if body is not None:
                    headers["Content-Type"] = "application/json"
                response = self._http.request(
                    method, f"{self.api_url}{path}", headers=headers, params=params, json=body
                )
        except httpx.HTTPError as exc:
            raise PIIShieldConnectionError(
                f"Could not reach PIIShield at {self.api_url}: {exc}"
            ) from exc
        if response.status_code >= 300:
            error = _core.error_from(response, context=context)
            if response.status_code == 503:
                raise PIIShieldConnectionError(error.message) from error
            raise error
        if raw:
            return response
        return response.json() if response.content else None

    # Detection

    def scan(self, text: str) -> ScanResult:
        """Detect PII in plain text without protecting it.

        ``POST /api/v1/detectors/scan``: a dedicated, side-effect-free detection route
        (no protection applied, no policy enforcement, so it never masks or writes an
        audit entry, unlike ``protect``). It also honours the project's custom
        recognizers, same as ``protect`` does.
        """
        body = {"project_id": self.project_id, "text": text}
        data = self._request("POST", "/api/v1/detectors/scan", body, context="scan")
        return ScanResult.from_api(data)

    def scan_json(self, payload: Any) -> ScanResult:
        """``scan``'s JSON counterpart: detects at every string leaf without protecting."""
        body = _core.protect_json_body(self.project_id, payload, None, ALL_CATEGORIES, None)
        data = self._request("POST", "/api/v1/protect/json", body, context="scan_json")
        return ScanResult.from_api(data)

    # Protection: one flexible call plus brief-exact convenience wrappers.
    # See the README's "Protection methods" section for why both exist.

    def mask(
        self,
        text: str,
        method: str = "full_mask",
        categories: list[str] | None = None,
        *,
        scope_id: str | None = None,
    ) -> ProtectionResult:
        """Protect text with one of four methods. ``POST /api/v1/protect/text``.

        ``method`` is one of ``"full_mask"`` (replace the whole value with a fixed mask),
        ``"partial_mask"`` (keep the policy's configured reveal count of characters),
        ``"redact"`` (remove the value, leave ``[REDACTED]``, no way to recover it from
        the response alone) or ``"tokenize"`` (replace with a stable placeholder like
        ``[EMAIL_001]``; the real value exists only in the encrypted vault). ``method``
        is applied as an override for every category named in ``categories`` (or, if
        ``categories`` is omitted, for every category PIIShield detects); categories not
        named keep the project policy's own configured method.

        Raises :class:`~euron_piishield.errors.PolicyViolationError` if ``method`` would
        leave a required category unmasked (it cannot: ``method_overrides`` always names
        a real masking method, never a skip, so this only happens via :meth:`redact`-style
        skip calls, kept for parity with the error's existence).
        """
        overrides = dict.fromkeys(categories or ALL_CATEGORIES, method)
        body = _core.protect_text_body(self.project_id, text, overrides, None, scope_id)
        data = self._request("POST", "/api/v1/protect/text", body, context="mask")
        return ProtectionResult.from_api(data)

    def mask_json(
        self,
        payload: Any,
        method: str = "full_mask",
        categories: list[str] | None = None,
        *,
        scope_id: str | None = None,
    ) -> ProtectionJsonResult:
        """``mask``'s JSON counterpart: protects every string leaf, preserves structure
        (AC7). ``POST /api/v1/protect/json``."""
        overrides = dict.fromkeys(categories or ALL_CATEGORIES, method)
        body = _core.protect_json_body(self.project_id, payload, overrides, None, scope_id)
        data = self._request("POST", "/api/v1/protect/json", body, context="mask_json")
        return ProtectionJsonResult.from_api(data)

    def redact(self, text: str, categories: list[str] | None = None) -> ProtectionResult:
        """``mask(text, method="redact", categories=categories)``."""
        return self.mask(text, "redact", categories)

    def anonymize(self, text: str, categories: list[str] | None = None) -> ProtectionResult:
        """``mask(text, method="full_mask", categories=categories)``, named for brief
        parity (the brief's ``/anonymize`` endpoint does not exist as a separate route on
        the real API; it is the same ``protect`` call as every other method)."""
        return self.mask(text, "full_mask", categories)

    def tokenize(
        self, text: str, scope_id: str | None = None, categories: list[str] | None = None
    ) -> ProtectionResult:
        """``mask(text, method="tokenize", scope_id=scope_id)``.

        Pass the same ``scope_id`` across calls (a request id or a named session) to get
        placeholder consistency: the same input value tokenized twice in one scope always
        yields the same placeholder, and two different values never collide (AC4). Omit
        ``scope_id`` and the server assigns a call-local scope (returned as
        ``result.scope_id``); pass that back on the next call to keep using the same one.
        """
        return self.mask(text, "tokenize", categories, scope_id=scope_id)

    def detokenize(self, placeholder: str, scope_id: str) -> DetokenizeResult:
        """Restore the original value behind one tokenize placeholder.
        ``POST /api/v1/vault/detokenize``.

        Requires the vault-access grant, a separate permission from the base API key,
        granted per user or per key with ``POST /api/v1/vault/grants`` (owner only). A
        caller without it gets :class:`~euron_piishield.errors.VaultPermissionError` on a
        403, never the original value and never a hint of it in the exception (AC5, AC6).
        """
        body = {"project_id": self.project_id, "placeholder": placeholder, "scope_id": scope_id}
        data = self._request("POST", "/api/v1/vault/detokenize", body, context="detokenize")
        return DetokenizeResult.from_api(data)

    # AI gateway

    def protect(self, prompt: str, scope_id: str | None = None) -> ProtectResult:
        """Protect a prompt before it reaches an external model.
        ``POST /api/v1/ai-gateway/protect``.

        Send only ``result.protected_text`` to the external AI provider. Keep
        ``result.scope_id`` server side or caller side: never forward it alongside the
        prompt to the model provider. See the README's "AI gateway safety property".
        """
        body: dict[str, Any] = {"project_id": self.project_id, "prompt": prompt}
        if scope_id is not None:
            body["scope_id"] = scope_id
        data = self._request("POST", "/api/v1/ai-gateway/protect", body, context="protect")
        return ProtectResult.from_api(data)

    def restore(self, scope_id: str, model_response_text: str) -> RestoreResult:
        """Restore placeholders in a model's response, for the calling application only.
        ``POST /api/v1/ai-gateway/restore``. The external model never sees ``restored_text``;
        only the application that called ``protect`` does, by presenting the same
        ``scope_id`` back here.
        """
        body = {
            "project_id": self.project_id,
            "scope_id": scope_id,
            "model_response": model_response_text,
        }
        data = self._request("POST", "/api/v1/ai-gateway/restore", body, context="restore")
        return RestoreResult.from_api(data)

    # Documents

    def protect_file(self, path_or_bytes: str | bytes | Path, filename: str | None = None) -> bytes:
        """Protect a PDF, DOCX, XLSX or CSV file, returned as the SAME file format
        (never a plain-text dump). ``POST /api/v1/documents``. The response is the raw
        protected file bytes; the caller writes them wherever the original came from.
        """
        content, name = _core.read_file_bytes(path_or_bytes, filename)
        _core.guess_content_type(name)  # validated client side; the server infers it too
        response = self._request(
            "POST",
            "/api/v1/documents",
            files={"file": (name, content)},
            params={"project_id": self.project_id},
            context="protect_file",
            raw=True,
        )
        return bytes(response.content)

    # Database scan

    def scan_database(
        self,
        connection_string: str,
        table_name: str,
        engine: str = "postgres",
        *,
        sample_rows: int = 200,
    ) -> DatabaseScanResult:
        """A read-only, column-level scan against a provided database connection.

        ``POST /api/v1/database-scan``. ``engine`` is one of ``"postgres"``, ``"mysql"``
        or ``"sqlite"``. Samples ``sample_rows`` rows of ``table_name`` and reports which
        columns look like they hold PII, with confidence, for a human to act on. The
        connection string is used once and never stored (not in the result row, not in
        the audit log); only ``table_name`` and the column findings persist. Never writes
        back to the database (0.1.0 does not anonymize a live database).
        """
        body = {
            "project_id": self.project_id,
            "engine": engine,
            "connection_string": connection_string,
            "table_name": table_name,
            "sample_rows": sample_rows,
        }
        data = self._request("POST", "/api/v1/database-scan", body, context="scan_database")
        return DatabaseScanResult.from_api(data)

    # Policies, reports, audit logs, review queue

    def get_policy(self) -> Policy:
        """``GET /api/v1/projects/{project_id}/policy``: this project's policy."""
        data = self._request(
            "GET", f"/api/v1/projects/{self.project_id}/policy", context="get_policy"
        )
        return Policy.from_api(data)

    def set_policy(
        self,
        *,
        required_categories: list[str] | None = None,
        masking_method: dict[str, str] | None = None,
        partial_mask_reveal: int = 4,
        confidence_threshold: float = 0.6,
        retention_days: int = 90,
    ) -> Policy:
        """``PUT /api/v1/projects/{project_id}/policy``: replace this project's policy."""
        body = {
            "required_categories": list(required_categories or []),
            "masking_method": dict(masking_method or {}),
            "partial_mask_reveal": partial_mask_reveal,
            "confidence_threshold": confidence_threshold,
            "retention_days": retention_days,
        }
        data = self._request(
            "PUT", f"/api/v1/projects/{self.project_id}/policy", body, context="set_policy"
        )
        return Policy.from_api(data)

    def get_audit_logs(self, *, limit: int = 50, action: str | None = None) -> AuditLogPage:
        """``GET /api/v1/audit``: a page of the append-only audit log. Never contains an
        original sensitive value (AC11)."""
        params: dict[str, Any] = {"limit": limit}
        if action is not None:
            params["action"] = action
        data = self._request("GET", "/api/v1/audit", context="get_audit_logs", params=params)
        return AuditLogPage.from_api(data)

    def get_review_items(self) -> list[ReviewItem]:
        """``GET /api/v1/review``: pending low-confidence findings for this project."""
        data = self._request(
            "GET",
            "/api/v1/review",
            context="get_review_items",
            params={"project_id": self.project_id},
        )
        return [ReviewItem.from_api(i) for i in data or []]

    def approve_review_item(self, item_id: str) -> ReviewItem:
        """``POST /api/v1/review/{item_id}/approve``."""
        data = self._request(
            "POST", f"/api/v1/review/{item_id}/approve", {}, context="approve_review_item"
        )
        return ReviewItem.from_api(data)

    def dismiss_review_item(self, item_id: str) -> ReviewItem:
        """``POST /api/v1/review/{item_id}/dismiss``."""
        data = self._request(
            "POST", f"/api/v1/review/{item_id}/dismiss", {}, context="dismiss_review_item"
        )
        return ReviewItem.from_api(data)
