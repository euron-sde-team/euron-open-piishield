"""Integration tests for the vault: AC4 (scope-consistent tokenization), AC5
(detokenization is permission-gated, separate from role/key scope), AC6 (the vault's
encrypted mapping never leaks into any scan/mask/redact/tokenize/ai_gateway response)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import second_client
from tests.integration.helpers import create_project, set_policy, signup

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_ac4_same_value_same_scope_same_placeholder(client: AsyncClient) -> None:
    await signup(client)
    project = await create_project(client)
    await set_policy(client, project["id"], masking_method={"contact": "tokenize"})

    first = await client.post(
        "/api/v1/protect/text",
        json={
            "project_id": project["id"],
            "text": "email jane@example.com",
            "scope_id": "ac4-scope",
        },
    )
    second = await client.post(
        "/api/v1/protect/text",
        json={
            "project_id": project["id"],
            "text": "jane@example.com again",
            "scope_id": "ac4-scope",
        },
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    first_placeholder = next(f["placeholder"] for f in first.json()["findings"] if f["placeholder"])
    second_placeholder = next(
        f["placeholder"] for f in second.json()["findings"] if f["placeholder"]
    )
    assert first_placeholder == second_placeholder == "[CONTACT_001]"


@pytest.mark.asyncio
async def test_ac4_different_values_never_collide_on_same_placeholder(
    client: AsyncClient,
) -> None:
    await signup(client)
    project = await create_project(client)
    await set_policy(client, project["id"], masking_method={"contact": "tokenize"})

    resp = await client.post(
        "/api/v1/protect/text",
        json={
            "project_id": project["id"],
            "text": "jane@example.com and john@example.com",
            "scope_id": "ac4-two-values",
        },
    )
    assert resp.status_code == 200, resp.text
    placeholders = [f["placeholder"] for f in resp.json()["findings"] if f["placeholder"]]
    assert len(placeholders) == 2
    assert len(set(placeholders)) == 2
    assert sorted(placeholders) == ["[CONTACT_001]", "[CONTACT_002]"]


@pytest.mark.asyncio
async def test_ac4_different_scope_gets_independent_numbering(client: AsyncClient) -> None:
    await signup(client)
    project = await create_project(client)
    await set_policy(client, project["id"], masking_method={"contact": "tokenize"})

    await client.post(
        "/api/v1/protect/text",
        json={
            "project_id": project["id"],
            "text": "jane@example.com",
            "scope_id": "scope-a",
        },
    )
    second = await client.post(
        "/api/v1/protect/text",
        json={
            "project_id": project["id"],
            "text": "jane@example.com",
            "scope_id": "scope-b",
        },
    )
    placeholder = next(f["placeholder"] for f in second.json()["findings"] if f["placeholder"])
    # A fresh scope starts its own placeholder numbering, independent of scope-a.
    assert placeholder == "[CONTACT_001]"


@pytest.mark.asyncio
async def test_ac5_detokenize_requires_vault_permission(client: AsyncClient, app: object) -> None:
    """A write-scoped project API key (admin-equivalent role) can tokenize, but cannot
    detokenize without a separate vault grant: AC5 says vault access is its own
    permission, never implied by role or key scope."""
    await signup(client)
    project = await create_project(client)
    await set_policy(client, project["id"], masking_method={"contact": "tokenize"})

    key_resp = await client.post(
        "/api/v1/auth/keys", json={"project_id": project["id"], "name": "writer", "scope": "write"}
    )
    assert key_resp.status_code == 201, key_resp.text
    write_key = key_resp.json()["key"]

    async with second_client(app) as scoped_client:
        scoped_client.headers["Authorization"] = f"Bearer {write_key}"
        protect_resp = await scoped_client.post(
            "/api/v1/protect/text",
            json={
                "project_id": project["id"],
                "text": "jane@example.com",
                "scope_id": "ac5-scope",
            },
        )
        assert protect_resp.status_code == 200, protect_resp.text
        placeholder = next(
            f["placeholder"] for f in protect_resp.json()["findings"] if f["placeholder"]
        )

        denied = await scoped_client.post(
            "/api/v1/vault/detokenize",
            json={
                "project_id": project["id"],
                "scope_id": "ac5-scope",
                "placeholder": placeholder,
            },
        )
        assert denied.status_code == 403, denied.text
        body = denied.json()
        assert body["error"]["code"] == "vault_access_required"
        # The denial never hints at the value, even in its error details.
        assert "jane@example.com" not in str(body)


@pytest.mark.asyncio
async def test_ac5_detokenize_succeeds_for_vault_access_holder(client: AsyncClient) -> None:
    """The signup owner is granted vault access by default (they created everything), so
    a plain owner session CAN detokenize: this is the positive side of AC5."""
    await signup(client)
    project = await create_project(client)
    await set_policy(client, project["id"], masking_method={"contact": "tokenize"})

    protect_resp = await client.post(
        "/api/v1/protect/text",
        json={
            "project_id": project["id"],
            "text": "jane@example.com",
            "scope_id": "ac5-owner-scope",
        },
    )
    placeholder = next(
        f["placeholder"] for f in protect_resp.json()["findings"] if f["placeholder"]
    )

    resp = await client.post(
        "/api/v1/vault/detokenize",
        json={
            "project_id": project["id"],
            "scope_id": "ac5-owner-scope",
            "placeholder": placeholder,
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["value"] == "jane@example.com"


@pytest.mark.asyncio
async def test_ac6_mapping_never_in_response(client: AsyncClient) -> None:
    """Scan/mask/redact/tokenize/ai_gateway responses never carry the vault's encrypted
    blob, nor the plaintext original, for a tokenized finding."""
    await signup(client)
    project = await create_project(client)
    await set_policy(
        client,
        project["id"],
        masking_method={"contact": "tokenize", "financial": "tokenize"},
    )

    secret_email = "secret.customer@example.com"
    secret_card = "4539148803436467"
    resp = await client.post(
        "/api/v1/protect/text",
        json={
            "project_id": project["id"],
            "text": f"contact {secret_email}, card {secret_card}",
            "scope_id": "ac6-scope",
        },
    )
    assert resp.status_code == 200, resp.text
    raw = resp.text
    assert secret_email not in raw
    assert secret_card not in raw
    # No field named anything that could hold a sealed blob or ciphertext.
    body = resp.json()
    assert "sealed_value" not in str(body)
    for finding in body["findings"]:
        assert set(finding.keys()) <= {
            "category",
            "start",
            "end",
            "confidence",
            "checksum_valid",
            "recognizer",
            "method",
            "placeholder",
            "in_review",
        }


@pytest.mark.asyncio
async def test_ac6_gateway_protect_response_never_carries_original_value(
    client: AsyncClient,
) -> None:
    await signup(client)
    project = await create_project(client)
    await set_policy(client, project["id"], masking_method={"financial": "tokenize"})

    secret_card = "4539148803436467"
    resp = await client.post(
        "/api/v1/ai-gateway/protect",
        json={
            "project_id": project["id"],
            "prompt": f"Please confirm card {secret_card}",
            "scope_id": "ac6-gateway-scope",
        },
    )
    assert resp.status_code == 200, resp.text
    assert secret_card not in resp.text
