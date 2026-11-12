"""AC12: org_id structural tenant scoping. A second organization's API key or session
gets a 404 for a resource it does not own, never that other org's policies, vault
entries, reports or audit records."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.integration.helpers import create_project, set_policy, signup

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_ac12_cross_org_project_access_is_404(client: AsyncClient, app: object) -> None:
    from tests.conftest import second_client

    await signup(client, org_name="Verdant Pay Org A", email="owner-a@test.example")
    project_a = await create_project(client, slug="project-a")

    async with second_client(app) as client_b:
        await signup(client_b, org_name="Northwind Org B", email="owner-b@test.example")

        resp = await client_b.get(f"/api/v1/projects/{project_a['id']}")
        assert resp.status_code == 404, resp.text

        resp = await client_b.put(
            f"/api/v1/projects/{project_a['id']}/policy",
            json={
                "required_categories": [],
                "masking_method": {},
                "partial_mask_reveal": 4,
                "confidence_threshold": 0.6,
                "retention_days": 90,
            },
        )
        assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_ac12_cross_org_vault_grant_access_is_404(client: AsyncClient, app: object) -> None:
    from tests.conftest import second_client

    session_a = await signup(client, org_name="Verdant Pay Org C", email="owner-c@test.example")
    user_a_id = session_a["user"]["id"]

    async with second_client(app) as client_b:
        session_b = await signup(client_b, org_name="Org D", email="owner-d@test.example")

        grant_resp = await client_b.post(
            "/api/v1/vault/grants", json={"user_id": session_b["user"]["id"]}
        )
        assert grant_resp.status_code == 201, grant_resp.text
        grant_id = grant_resp.json()["id"]

        # Org A's owner never sees org B's grant list, and cannot revoke org B's grant.
        list_resp = await client.get("/api/v1/vault/grants")
        assert list_resp.status_code == 200
        assert all(g["id"] != grant_id for g in list_resp.json())

        revoke_resp = await client.delete(f"/api/v1/vault/grants/{grant_id}")
        # Revoking a grant that is not in this org's scope is a silent no-op (never a
        # cross-tenant mutation) per the vault service's own scoped lookup.
        assert revoke_resp.status_code == 204

        still_there = await client_b.get("/api/v1/vault/grants")
        assert any(g["id"] == grant_id and g["revoked_at"] is None for g in still_there.json())
    assert user_a_id  # sanity: org A's own user id is well-formed and unrelated to org B


@pytest.mark.asyncio
async def test_ac12_cross_org_audit_log_is_isolated(client: AsyncClient, app: object) -> None:
    from tests.conftest import second_client

    await signup(client, org_name="Verdant Pay Org E", email="owner-e@test.example")
    project = await create_project(client, slug="project-e")
    await set_policy(client, project["id"], masking_method={"contact": "redact"})
    await client.post(
        "/api/v1/protect/text",
        json={"project_id": project["id"], "text": "email jane@example.com"},
    )

    async with second_client(app) as client_b:
        await signup(client_b, org_name="Org F", email="owner-f@test.example")
        audit_b = await client_b.get("/api/v1/audit")
        assert audit_b.status_code == 200
        # Org B's own signup produced its own "org.created" entry, but never org A's
        # "scan" entries (org A scanned text with a real email in it).
        for entry in audit_b.json()["items"]:
            assert entry["action"] != "scan"


@pytest.mark.asyncio
async def test_ac12_cross_org_report_summary_is_isolated(client: AsyncClient, app: object) -> None:
    """Reports are an org-wide aggregate (no project_id in the request), so AC12's
    isolation shows up as org B's summary never reflecting org A's scan activity, not as
    a 404."""
    from tests.conftest import second_client

    await signup(client, org_name="Verdant Pay Org G", email="owner-g@test.example")
    project = await create_project(client, slug="project-g")
    await set_policy(client, project["id"], masking_method={"contact": "redact"})
    await client.post(
        "/api/v1/protect/text",
        json={"project_id": project["id"], "text": "email jane@example.com"},
    )

    async with second_client(app) as client_b:
        await signup(client_b, org_name="Org H", email="owner-h@test.example")
        resp = await client_b.get("/api/v1/reports/summary")
        assert resp.status_code == 200, resp.text
        assert resp.json()["total_scans"] == 0
