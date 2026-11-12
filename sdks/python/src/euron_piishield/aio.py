"""The asynchronous client: ``AsyncPIIShield`` (the same methods as ``PIIShield``, awaited)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from euron_piishield import _core
from euron_piishield.client import ALL_CATEGORIES
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


class AsyncPIIShield:
    """The async counterpart of :class:`~euron_piishield.PIIShield`. Same methods, awaited.

    ::

        async with AsyncPIIShield(
            api_url="http://localhost:8000", api_key="KEY", project_id="..."
        ) as shield:
            result = await shield.mask("Email: rahul@example.com")

    Safe to share between tasks of one event loop.
    """

    def __init__(
        self,
        api_url: str,
        api_key: str,
        project_id: str,
        *,
        timeout: float = 30.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_url = _core.check_options(api_url, api_key)
        self.api_key = api_key
        self.project_id = project_id
        self.timeout = timeout
        self._own_http = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        if self._own_http:
            await self._http.aclose()

    async def __aenter__(self) -> AsyncPIIShield:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "User-Agent": _core.USER_AGENT}

    async def _request(
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
                response = await self._http.request(
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
                response = await self._http.request(
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

    async def scan(self, text: str) -> ScanResult:
        """See :meth:`~euron_piishield.client.PIIShield.scan`: a dedicated,
        side-effect-free detection call, ``POST /api/v1/detectors/scan``."""
        body = {"project_id": self.project_id, "text": text}
        data = await self._request("POST", "/api/v1/detectors/scan", body, context="scan")
        return ScanResult.from_api(data)

    async def scan_json(self, payload: Any) -> ScanResult:
        body = _core.protect_json_body(self.project_id, payload, None, ALL_CATEGORIES, None)
        data = await self._request("POST", "/api/v1/protect/json", body, context="scan_json")
        return ScanResult.from_api(data)

    async def mask(
        self,
        text: str,
        method: str = "full_mask",
        categories: list[str] | None = None,
        *,
        scope_id: str | None = None,
    ) -> ProtectionResult:
        overrides = dict.fromkeys(categories or ALL_CATEGORIES, method)
        body = _core.protect_text_body(self.project_id, text, overrides, None, scope_id)
        data = await self._request("POST", "/api/v1/protect/text", body, context="mask")
        return ProtectionResult.from_api(data)

    async def mask_json(
        self,
        payload: Any,
        method: str = "full_mask",
        categories: list[str] | None = None,
        *,
        scope_id: str | None = None,
    ) -> ProtectionJsonResult:
        overrides = dict.fromkeys(categories or ALL_CATEGORIES, method)
        body = _core.protect_json_body(self.project_id, payload, overrides, None, scope_id)
        data = await self._request("POST", "/api/v1/protect/json", body, context="mask_json")
        return ProtectionJsonResult.from_api(data)

    async def redact(self, text: str, categories: list[str] | None = None) -> ProtectionResult:
        return await self.mask(text, "redact", categories)

    async def anonymize(self, text: str, categories: list[str] | None = None) -> ProtectionResult:
        return await self.mask(text, "full_mask", categories)

    async def tokenize(
        self, text: str, scope_id: str | None = None, categories: list[str] | None = None
    ) -> ProtectionResult:
        return await self.mask(text, "tokenize", categories, scope_id=scope_id)

    async def detokenize(self, placeholder: str, scope_id: str) -> DetokenizeResult:
        body = {"project_id": self.project_id, "placeholder": placeholder, "scope_id": scope_id}
        data = await self._request("POST", "/api/v1/vault/detokenize", body, context="detokenize")
        return DetokenizeResult.from_api(data)

    async def protect(self, prompt: str, scope_id: str | None = None) -> ProtectResult:
        body: dict[str, Any] = {"project_id": self.project_id, "prompt": prompt}
        if scope_id is not None:
            body["scope_id"] = scope_id
        data = await self._request("POST", "/api/v1/ai-gateway/protect", body, context="protect")
        return ProtectResult.from_api(data)

    async def restore(self, scope_id: str, model_response_text: str) -> RestoreResult:
        body = {
            "project_id": self.project_id,
            "scope_id": scope_id,
            "model_response": model_response_text,
        }
        data = await self._request("POST", "/api/v1/ai-gateway/restore", body, context="restore")
        return RestoreResult.from_api(data)

    async def protect_file(
        self, path_or_bytes: str | bytes | Path, filename: str | None = None
    ) -> bytes:
        content, name = _core.read_file_bytes(path_or_bytes, filename)
        _core.guess_content_type(name)
        response = await self._request(
            "POST",
            "/api/v1/documents",
            files={"file": (name, content)},
            params={"project_id": self.project_id},
            context="protect_file",
            raw=True,
        )
        return bytes(response.content)

    async def scan_database(
        self,
        connection_string: str,
        table_name: str,
        engine: str = "postgres",
        *,
        sample_rows: int = 200,
    ) -> DatabaseScanResult:
        body = {
            "project_id": self.project_id,
            "engine": engine,
            "connection_string": connection_string,
            "table_name": table_name,
            "sample_rows": sample_rows,
        }
        data = await self._request("POST", "/api/v1/database-scan", body, context="scan_database")
        return DatabaseScanResult.from_api(data)

    async def get_policy(self) -> Policy:
        data = await self._request(
            "GET", f"/api/v1/projects/{self.project_id}/policy", context="get_policy"
        )
        return Policy.from_api(data)

    async def set_policy(
        self,
        *,
        required_categories: list[str] | None = None,
        masking_method: dict[str, str] | None = None,
        partial_mask_reveal: int = 4,
        confidence_threshold: float = 0.6,
        retention_days: int = 90,
    ) -> Policy:
        body = {
            "required_categories": list(required_categories or []),
            "masking_method": dict(masking_method or {}),
            "partial_mask_reveal": partial_mask_reveal,
            "confidence_threshold": confidence_threshold,
            "retention_days": retention_days,
        }
        data = await self._request(
            "PUT", f"/api/v1/projects/{self.project_id}/policy", body, context="set_policy"
        )
        return Policy.from_api(data)

    async def get_audit_logs(self, *, limit: int = 50, action: str | None = None) -> AuditLogPage:
        params: dict[str, Any] = {"limit": limit}
        if action is not None:
            params["action"] = action
        data = await self._request("GET", "/api/v1/audit", context="get_audit_logs", params=params)
        return AuditLogPage.from_api(data)

    async def get_review_items(self) -> list[ReviewItem]:
        data = await self._request(
            "GET",
            "/api/v1/review",
            context="get_review_items",
            params={"project_id": self.project_id},
        )
        return [ReviewItem.from_api(i) for i in data or []]

    async def approve_review_item(self, item_id: str) -> ReviewItem:
        data = await self._request(
            "POST", f"/api/v1/review/{item_id}/approve", {}, context="approve_review_item"
        )
        return ReviewItem.from_api(data)

    async def dismiss_review_item(self, item_id: str) -> ReviewItem:
        data = await self._request(
            "POST", f"/api/v1/review/{item_id}/dismiss", {}, context="dismiss_review_item"
        )
        return ReviewItem.from_api(data)
