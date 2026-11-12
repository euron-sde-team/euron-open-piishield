"""AC13: a finding below the policy's confidence threshold lands in the review_items
table (listed by the review queue) instead of only being auto-protected, unless its
category is required (then it is both protected per AC10 and flagged for review)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.integration.helpers import create_project, set_policy, signup

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_ac13_low_confidence_finding_goes_to_review_queue(client: AsyncClient) -> None:
    """``bank_account`` has a base confidence of 0.3, well under the 0.6 default
    threshold, and "financial" is not marked required here, so the plain digit string is
    left unmasked in the output and instead queued for a human decision."""
    await signup(client)
    project = await create_project(client)
    await set_policy(client, project["id"], threshold=0.6)

    resp = await client.post(
        "/api/v1/protect/text",
        json={"project_id": project["id"], "text": "account number 000123456789 on file"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["review_count"] >= 1
    in_review = [f for f in body["findings"] if f["in_review"]]
    assert any(f["category"] == "financial" for f in in_review)

    queue = await client.get("/api/v1/review", params={"project_id": project["id"]})
    assert queue.status_code == 200, queue.text
    items = queue.json()
    assert len(items) >= 1
    assert all(item["status"] == "pending" for item in items)
    assert any(item["category"] == "financial" for item in items)


@pytest.mark.asyncio
async def test_ac13_required_category_is_protected_and_still_flagged(
    client: AsyncClient,
) -> None:
    """AC10's required-category rule still protects a low-confidence required-category
    finding (never silently passed through raw), but PLAN.md's request lifecycle step 3
    says it is ALSO flagged for review."""
    await signup(client)
    project = await create_project(client)
    await set_policy(
        client,
        project["id"],
        required=["financial"],
        masking_method={"financial": "redact"},
        threshold=0.6,
    )

    resp = await client.post(
        "/api/v1/protect/text",
        json={"project_id": project["id"], "text": "account number 000123456789 on file"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    financial = [f for f in body["findings"] if f["category"] == "financial"]
    assert financial, "expected a financial finding"
    assert financial[0]["in_review"] is True
    assert "000123456789" not in body["protected"]

    queue = await client.get("/api/v1/review", params={"project_id": project["id"]})
    items = queue.json()
    matching = [i for i in items if i["category"] == "financial"]
    assert matching
    assert matching[0]["already_protected"] is True


@pytest.mark.asyncio
async def test_ac13_approve_marks_item_decided(client: AsyncClient) -> None:
    await signup(client)
    project = await create_project(client)
    await set_policy(client, project["id"], threshold=0.6)
    await client.post(
        "/api/v1/protect/text",
        json={"project_id": project["id"], "text": "account number 000123456789 on file"},
    )
    queue = await client.get("/api/v1/review", params={"project_id": project["id"]})
    item_id = queue.json()[0]["id"]

    resp = await client.post(f"/api/v1/review/{item_id}/approve")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "approved"
    assert resp.json()["decided_at"] is not None

    # Deciding twice is refused, not silently re-applied.
    again = await client.post(f"/api/v1/review/{item_id}/approve")
    assert again.status_code == 409, again.text


@pytest.mark.asyncio
async def test_ac13_dismiss_marks_item_decided(client: AsyncClient) -> None:
    await signup(client)
    project = await create_project(client)
    await set_policy(client, project["id"], threshold=0.6)
    await client.post(
        "/api/v1/protect/text",
        json={"project_id": project["id"], "text": "account number 000123456789 on file"},
    )
    queue = await client.get("/api/v1/review", params={"project_id": project["id"]})
    item_id = queue.json()[0]["id"]

    resp = await client.post(f"/api/v1/review/{item_id}/dismiss")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "dismissed"

    pending = await client.get("/api/v1/review", params={"project_id": project["id"]})
    assert all(i["id"] != item_id for i in pending.json())
