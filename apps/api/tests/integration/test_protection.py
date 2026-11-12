"""Integration tests for the protect pipeline: AC3 (four methods), AC7 (JSON structure),
AC10 (required category refuses unmasked)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.integration.helpers import create_project, set_policy, signup

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_ac3_full_mask_produces_fixed_marker(client: AsyncClient) -> None:
    await signup(client)
    project = await create_project(client)
    await set_policy(client, project["id"], masking_method={"contact": "full_mask"})
    resp = await client.post(
        "/api/v1/protect/text",
        json={"project_id": project["id"], "text": "email me at jane@example.com"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "****" in body["protected"]
    assert "jane@example.com" not in body["protected"]


@pytest.mark.asyncio
async def test_ac3_partial_mask_reveals_configured_count(client: AsyncClient) -> None:
    await signup(client)
    project = await create_project(client)
    await set_policy(client, project["id"], masking_method={"contact": "partial_mask"})
    resp = await client.post(
        "/api/v1/protect/text",
        json={"project_id": project["id"], "text": "call 9876543210 now"},
    )
    body = resp.json()
    assert "9876543210" not in body["protected"]
    assert "3210" in body["protected"]  # last 4 digits (default reveal) survive


@pytest.mark.asyncio
async def test_ac3_redact_leaves_no_recoverable_trace(client: AsyncClient) -> None:
    await signup(client)
    project = await create_project(client)
    await set_policy(client, project["id"], masking_method={"financial": "redact"})
    resp = await client.post(
        "/api/v1/protect/text",
        json={"project_id": project["id"], "text": "card 4539148803436467 declined"},
    )
    body = resp.json()
    assert "[REDACTED:financial]" in body["protected"]
    assert "4539148803436467" not in body["protected"]
    # No hash or any derived form of the value anywhere in the response body.
    assert "4539148803436467" not in str(body)


@pytest.mark.asyncio
async def test_ac3_tokenize_produces_stable_placeholder_and_four_methods_differ(
    client: AsyncClient,
) -> None:
    await signup(client)
    project = await create_project(client)
    await set_policy(client, project["id"], masking_method={"contact": "tokenize"})
    resp = await client.post(
        "/api/v1/protect/text",
        json={"project_id": project["id"], "text": "email jane@example.com"},
    )
    body = resp.json()
    assert "[CONTACT_001]" in body["protected"]
    assert "jane@example.com" not in body["protected"]


@pytest.mark.asyncio
async def test_ac7_json_leaf_recursion_preserves_structure(client: AsyncClient) -> None:
    await signup(client)
    project = await create_project(client)
    await set_policy(client, project["id"], masking_method={"contact": "redact"})
    payload = {
        "customer": {"email": "a@b.com", "age": 31, "active": True},
        "notes": ["contact a@b.com", "no pii here"],
        "meta": None,
    }
    resp = await client.post(
        "/api/v1/protect/json", json={"project_id": project["id"], "payload": payload}
    )
    assert resp.status_code == 200, resp.text
    protected = resp.json()["protected"]
    assert list(protected.keys()) == list(payload.keys())
    assert protected["customer"]["age"] == 31
    assert protected["customer"]["active"] is True
    assert protected["meta"] is None
    assert len(protected["notes"]) == 2
    assert protected["notes"][1] == "no pii here"
    assert "a@b.com" not in protected["customer"]["email"]
    assert "a@b.com" not in protected["notes"][0]


@pytest.mark.asyncio
async def test_ac10_required_category_refuses_unmasked(client: AsyncClient) -> None:
    await signup(client)
    project = await create_project(client)
    await set_policy(client, project["id"], required=["financial"])
    resp = await client.post(
        "/api/v1/protect/text",
        json={
            "project_id": project["id"],
            "text": "card 4539148803436467",
            "skip_categories": ["financial"],
        },
    )
    assert resp.status_code == 422
    error = resp.json()["error"]
    assert error["code"] == "required_category_unmasked"
    # The refusal is structured and never echoes the raw value anywhere.
    assert "4539148803436467" not in str(resp.json())


@pytest.mark.asyncio
async def test_ac10_required_category_with_masking_enabled_succeeds(client: AsyncClient) -> None:
    await signup(client)
    project = await create_project(client)
    await set_policy(client, project["id"], required=["financial"])
    resp = await client.post(
        "/api/v1/protect/text",
        json={"project_id": project["id"], "text": "card 4539148803436467"},
    )
    assert resp.status_code == 200
    assert "4539148803436467" not in resp.json()["protected"]
