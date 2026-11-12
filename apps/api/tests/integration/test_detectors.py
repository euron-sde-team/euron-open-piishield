"""Integration coverage for plain scanning (no protection applied) and AC2's per-project
custom-pattern recognizer, end to end through the API: create a custom pattern, scan text
that matches it, confirm it is reported with the right category, and confirm a disabled
recognizer stops matching."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.integration.helpers import create_project, signup

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_scan_endpoint_reports_findings_without_protecting(client: AsyncClient) -> None:
    await signup(client)
    project = await create_project(client)
    resp = await client.post(
        "/api/v1/detectors/scan",
        json={"project_id": project["id"], "text": "email jane@example.com"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["findings"]) == 1
    assert body["findings"][0]["category"] == "contact"
    # Plain scanning never masks anything: the matched text was never echoed back in the
    # response in the first place (the endpoint has no "protected" field at all), only
    # offsets and metadata.
    assert set(body["findings"][0].keys()) == {
        "category",
        "start",
        "end",
        "confidence",
        "checksum_valid",
        "recognizer",
    }


@pytest.mark.asyncio
async def test_ac2_custom_recognizer_end_to_end(client: AsyncClient) -> None:
    await signup(client)
    project = await create_project(client)

    create_resp = await client.post(
        "/api/v1/detectors/recognizers",
        json={
            "project_id": project["id"],
            "name": "support_ticket_id",
            "category": "custom",
            "pattern": r"\bTCK-\d{6}\b",
            "confidence": 0.8,
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    recognizer = create_resp.json()
    assert recognizer["enabled"] is True

    list_resp = await client.get(
        "/api/v1/detectors/recognizers", params={"project_id": project["id"]}
    )
    assert list_resp.status_code == 200
    assert any(r["id"] == recognizer["id"] for r in list_resp.json())

    scan_resp = await client.post(
        "/api/v1/detectors/scan",
        json={"project_id": project["id"], "text": "Ticket TCK-482913 is open"},
    )
    assert scan_resp.status_code == 200, scan_resp.text
    custom_findings = [f for f in scan_resp.json()["findings"] if f["category"] == "custom"]
    assert len(custom_findings) == 1
    assert custom_findings[0]["recognizer"] == "support_ticket_id"

    delete_resp = await client.delete(f"/api/v1/detectors/recognizers/{recognizer['id']}")
    assert delete_resp.status_code == 204

    scan_after_delete = await client.post(
        "/api/v1/detectors/scan",
        json={"project_id": project["id"], "text": "Ticket TCK-482913 is open"},
    )
    custom_after = [f for f in scan_after_delete.json()["findings"] if f["category"] == "custom"]
    assert custom_after == []


@pytest.mark.asyncio
async def test_ac2_custom_recognizer_is_scoped_to_its_own_project(client: AsyncClient) -> None:
    await signup(client)
    project_a = await create_project(client, slug="project-a")
    project_b = await create_project(client, slug="project-b")

    await client.post(
        "/api/v1/detectors/recognizers",
        json={
            "project_id": project_a["id"],
            "name": "order_id",
            "category": "custom",
            "pattern": r"\bORD-\d{5}\b",
            "confidence": 0.8,
        },
    )

    scan_b = await client.post(
        "/api/v1/detectors/scan",
        json={"project_id": project_b["id"], "text": "Order ORD-12345 shipped"},
    )
    assert scan_b.status_code == 200, scan_b.text
    assert all(f["category"] != "custom" for f in scan_b.json()["findings"])
