"""Integration coverage for /metrics: a real scan actually increments a real counter,
not just that the route returns 200. Prometheus's default registry is process-global,
so this asserts the exposition text contains the metric and its labels, never an
absolute value (other tests in the same process may have already incremented it)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.integration.helpers import create_project, signup

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_metrics_exposes_prometheus_text(client: AsyncClient) -> None:
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")


@pytest.mark.asyncio
async def test_a_real_scan_increments_the_findings_counter(client: AsyncClient) -> None:
    await signup(client)
    project = await create_project(client)
    await client.post(
        "/api/v1/detectors/scan",
        json={"project_id": project["id"], "text": "email jane@example.com"},
    )
    resp = await client.get("/metrics")
    body = resp.text
    assert 'piishield_scans_total{source="detectors_scan"}' in body
    assert 'piishield_findings_total{category="contact"}' in body
