"""Shared integration-test helpers: signup, project+policy setup."""

from __future__ import annotations

from typing import Any

from httpx import AsyncClient


async def signup(
    client: AsyncClient, org_name: str = "Verdant Pay Test", email: str = "owner@test.example"
) -> dict[str, Any]:
    resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "org_name": org_name,
            "name": "Test Owner",
            "email": email,
            "password": "Str0ngPassw0rd!",
        },
    )
    assert resp.status_code == 201, resp.text
    data: dict[str, Any] = resp.json()
    client.headers["Authorization"] = f"Bearer {data['token']}"
    return data


async def create_project(client: AsyncClient, slug: str = "default") -> dict[str, Any]:
    resp = await client.post("/api/v1/projects", json={"name": slug.title(), "slug": slug})
    assert resp.status_code == 201, resp.text
    data: dict[str, Any] = resp.json()
    return data


async def set_policy(
    client: AsyncClient,
    project_id: str,
    required: list[str] | None = None,
    masking_method: dict[str, str] | None = None,
    threshold: float = 0.6,
) -> None:
    resp = await client.put(
        f"/api/v1/projects/{project_id}/policy",
        json={
            "required_categories": required or [],
            "masking_method": masking_method or {},
            "partial_mask_reveal": 4,
            "confidence_threshold": threshold,
            "retention_days": 90,
        },
    )
    assert resp.status_code == 200, resp.text
