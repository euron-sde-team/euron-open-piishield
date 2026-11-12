"""The async client: same contract as the sync client, awaited."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import respx

from euron_piishield import AsyncPIIShield, VaultPermissionError

from .helpers import API_KEY, BASE, PROJECT_ID, error_body, protect_text_response, scan_response


@pytest.fixture
def api() -> Any:
    with respx.mock(base_url=BASE, assert_all_called=False) as router:
        yield router


@pytest.fixture
async def shield() -> AsyncIterator[AsyncPIIShield]:
    client = AsyncPIIShield(BASE, API_KEY, PROJECT_ID)
    yield client
    await client.aclose()


def _body(request: httpx.Request) -> Any:
    return json.loads(request.content)


async def test_scan_parses_findings(api: respx.MockRouter, shield: AsyncPIIShield) -> None:
    route = api.post("/api/v1/detectors/scan").mock(
        return_value=httpx.Response(
            200,
            json=scan_response(
                {
                    "category": "contact",
                    "start": 0,
                    "end": 5,
                    "confidence": 0.9,
                    "checksum_valid": None,
                    "recognizer": "email",
                },
            ),
        )
    )
    result = await shield.scan("x@y.z")
    assert _body(route.calls.last.request) == {"project_id": PROJECT_ID, "text": "x@y.z"}
    assert result.findings[0].category == "contact"
    assert result.findings[0].recognizer == "email"


async def test_tokenize_scope_round_trip(api: respx.MockRouter, shield: AsyncPIIShield) -> None:
    route = api.post("/api/v1/protect/text").mock(
        return_value=httpx.Response(200, json=protect_text_response("[EMAIL_001]", scope_id="s1"))
    )
    result = await shield.tokenize("a@example.com", scope_id="s1")
    assert _body(route.calls.last.request)["scope_id"] == "s1"
    assert result.scope_id == "s1"


async def test_detokenize_403_raises_vault_permission_error(
    api: respx.MockRouter, shield: AsyncPIIShield
) -> None:
    api.post("/api/v1/vault/detokenize").mock(
        return_value=httpx.Response(403, json=error_body("vault_access_required"))
    )
    with pytest.raises(VaultPermissionError):
        await shield.detokenize("[EMAIL_001]", "s1")


async def test_protect_restore_round_trip(api: respx.MockRouter, shield: AsyncPIIShield) -> None:
    api.post("/api/v1/ai-gateway/protect").mock(
        return_value=httpx.Response(
            200,
            json={
                "protected_prompt": "My card is [CARD_001].",
                "scope_id": "scope-1",
                "findings": [],
            },
        )
    )
    api.post("/api/v1/ai-gateway/restore").mock(
        return_value=httpx.Response(
            200,
            json={
                "restored_response": "Your card 4111111111111111 is valid.",
                "placeholders_restored": 1,
            },
        )
    )
    protected = await shield.protect("My card is 4111111111111111.")
    assert protected.scope_id == "scope-1"
    restored = await shield.restore(protected.scope_id, "Your card [CARD_001] is valid.")
    assert "4111111111111111" in restored.restored_text
