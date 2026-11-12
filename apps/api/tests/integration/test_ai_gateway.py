"""AC9: the AI gateway protects a prompt before it would reach an external model, returns
the protected prompt plus a per-call token map reference (``scope_id``), and a caller can
submit the model's response for restoration back to the real values, for the calling
application only, never for the external model."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.integration.helpers import create_project, set_policy, signup

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_ac9_protect_then_restore_round_trip(client: AsyncClient) -> None:
    await signup(client)
    project = await create_project(client)
    await set_policy(
        client, project["id"], masking_method={"contact": "tokenize", "financial": "tokenize"}
    )

    secret_email = "ananya.gupta@verdantpay.example"
    secret_card = "4539148803436467"
    prompt = f"Please confirm the refund for {secret_email}, card {secret_card}."

    protect_resp = await client.post(
        "/api/v1/ai-gateway/protect",
        json={"project_id": project["id"], "prompt": prompt, "scope_id": "gw-round-trip"},
    )
    assert protect_resp.status_code == 200, protect_resp.text
    protected = protect_resp.json()

    # The protected prompt (what an external model would actually see) never carries the
    # original values.
    assert secret_email not in protected["protected_prompt"]
    assert secret_card not in protected["protected_prompt"]
    assert protected["scope_id"] == "gw-round-trip"
    assert len(protected["findings"]) == 2

    # Simulate the external model's response, which echoes the placeholders back (as a
    # real model asked to "confirm" would plausibly do).
    model_response = (
        f"Confirmed for {protected['findings'][0]['placeholder']} and "
        f"{protected['findings'][1]['placeholder']}. Refund processed."
    )

    restore_resp = await client.post(
        "/api/v1/ai-gateway/restore",
        json={
            "project_id": project["id"],
            "scope_id": protected["scope_id"],
            "model_response": model_response,
        },
    )
    assert restore_resp.status_code == 200, restore_resp.text
    restored = restore_resp.json()
    assert restored["placeholders_restored"] == 2
    assert secret_email in restored["restored_response"]
    assert secret_card in restored["restored_response"]


@pytest.mark.asyncio
async def test_ac9_external_model_never_sees_a_restore_call(client: AsyncClient) -> None:
    """The mock AI service is a real, separate HTTP service that only ever receives the
    protected prompt text; it has no restore endpoint and no way to resolve a placeholder,
    proving the external-model boundary by construction rather than by convention."""
    import os

    import httpx

    await signup(client)
    project = await create_project(client)
    await set_policy(client, project["id"], masking_method={"financial": "tokenize"})

    secret_card = "4539148803436467"
    protect_resp = await client.post(
        "/api/v1/ai-gateway/protect",
        json={
            "project_id": project["id"],
            "prompt": f"Confirm card {secret_card}",
            "scope_id": "gw-external-model",
        },
    )
    protected = protect_resp.json()

    mock_ai_url = os.environ.get("TEST_MOCKAI_URL", "http://localhost:5550")
    async with httpx.AsyncClient(base_url=mock_ai_url, timeout=10.0) as ai_client:
        try:
            resp = await ai_client.post(
                "/v1/complete", json={"prompt": protected["protected_prompt"]}
            )
        except httpx.ConnectError:
            pytest.skip("mock AI service is not reachable from this test run")
            return
        assert resp.status_code == 200
        model_text = resp.text
        # The mock model's own HTTP response never contains the original card number: it
        # only ever saw the protected prompt.
        assert secret_card not in model_text
        # And the mock model has no restore route at all.
        missing = await ai_client.post("/v1/restore", json={})
        assert missing.status_code == 404


@pytest.mark.asyncio
async def test_ac9_restore_scoped_to_its_own_scope_id(client: AsyncClient) -> None:
    """Restoring against a scope_id that never had a matching protect call (or a
    placeholder from a different scope) restores nothing for that placeholder, it is left
    as-is rather than resolved from an unrelated scope's vault entries."""
    await signup(client)
    project = await create_project(client)
    await set_policy(client, project["id"], masking_method={"financial": "tokenize"})

    await client.post(
        "/api/v1/ai-gateway/protect",
        json={
            "project_id": project["id"],
            "prompt": "Card 4539148803436467",
            "scope_id": "gw-scope-one",
        },
    )

    resp = await client.post(
        "/api/v1/ai-gateway/restore",
        json={
            "project_id": project["id"],
            "scope_id": "gw-scope-two-unrelated",
            "model_response": "Confirmed for [FINANCIAL_001].",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["placeholders_restored"] == 0
    assert body["restored_response"] == "Confirmed for [FINANCIAL_001]."
