"""Policy CRUD and AC10's structured refusal when a required category's masking is
explicitly disabled for one call."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.integration.helpers import create_project, set_policy, signup

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_policy_get_returns_404_before_any_write(client: AsyncClient) -> None:
    await signup(client)
    project = await create_project(client)
    resp = await client.get(f"/api/v1/projects/{project['id']}/policy")
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_policy_put_then_get_round_trips(client: AsyncClient) -> None:
    await signup(client)
    project = await create_project(client)
    put_resp = await client.put(
        f"/api/v1/projects/{project['id']}/policy",
        json={
            "required_categories": ["financial"],
            "masking_method": {"financial": "tokenize", "contact": "partial_mask"},
            "partial_mask_reveal": 3,
            "confidence_threshold": 0.7,
            "retention_days": 30,
        },
    )
    assert put_resp.status_code == 200, put_resp.text
    body = put_resp.json()
    assert body["required_categories"] == ["financial"]
    assert body["partial_mask_reveal"] == 3
    assert body["confidence_threshold"] == 0.7
    assert body["retention_days"] == 30

    get_resp = await client.get(f"/api/v1/projects/{project['id']}/policy")
    assert get_resp.status_code == 200
    assert get_resp.json() == body


@pytest.mark.asyncio
async def test_policy_put_rejects_unknown_fields(client: AsyncClient) -> None:
    await signup(client)
    project = await create_project(client)
    resp = await client.put(
        f"/api/v1/projects/{project['id']}/policy",
        json={
            "required_categories": [],
            "masking_method": {},
            "partial_mask_reveal": 4,
            "confidence_threshold": 0.6,
            "retention_days": 90,
            "unexpected_field": "nope",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ac10_required_category_refusal_has_structured_error_body(
    client: AsyncClient,
) -> None:
    await signup(client)
    project = await create_project(client)
    await set_policy(client, project["id"], required=["government_id"])

    resp = await client.post(
        "/api/v1/protect/text",
        json={
            "project_id": project["id"],
            "text": "Aadhaar 234123412346",
            "skip_categories": ["government_id"],
        },
    )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert set(body.keys()) == {"error"}
    assert set(body["error"].keys()) == {"code", "type", "message", "details"}
    assert body["error"]["code"] == "required_category_unmasked"
    # The raw Aadhaar number never survives into the structured error (not even in the
    # error's own details, which other endpoints use for debugging context).
    assert "234123412346" not in str(body)


@pytest.mark.asyncio
async def test_ac10_non_required_category_may_be_skipped(client: AsyncClient) -> None:
    """Skipping a category that is NOT marked required is a legitimate, documented
    choice, not a refusal: only a required category with masking disabled is refused."""
    await signup(client)
    project = await create_project(client)
    await set_policy(client, project["id"], required=["government_id"])

    resp = await client.post(
        "/api/v1/protect/text",
        json={
            "project_id": project["id"],
            "text": "email jane@example.com",
            "skip_categories": ["contact"],
        },
    )
    assert resp.status_code == 200, resp.text
    assert "jane@example.com" in resp.json()["protected"]


@pytest.mark.asyncio
async def test_default_policy_tokenizes_when_none_was_ever_set(client: AsyncClient) -> None:
    """0.1.0's built-in default (no policy row created yet) is "nothing required,
    tokenize everything", per policies/service.py's ``_DEFAULT`` snapshot."""
    await signup(client)
    project = await create_project(client)

    resp = await client.post(
        "/api/v1/protect/text",
        json={"project_id": project["id"], "text": "email jane@example.com"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "jane@example.com" not in body["protected"]
    assert "[CONTACT_001]" in body["protected"]
