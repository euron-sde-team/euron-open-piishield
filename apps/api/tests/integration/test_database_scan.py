"""The read-only, column-level database scan: samples rows from a caller-provided
connection and reports which columns look like they hold PII, without writing to or
persisting a sample of the scanned database. Uses a real, throwaway SQLite file so this
test needs no extra Docker service."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from httpx import AsyncClient

from tests.integration.helpers import create_project, signup

pytestmark = pytest.mark.integration


@pytest.fixture
def sqlite_db_path(tmp_path: Path) -> str:
    db_path = tmp_path / "merchant.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, email TEXT, notes TEXT)")
    conn.executemany(
        "INSERT INTO customers (email, notes) VALUES (?, ?)",
        [
            ("ananya.gupta@example.com", "no special notes"),
            ("rohan.verma@example.com", "prefers email contact"),
            ("priya.nair@example.com", "VIP customer"),
        ],
    )
    conn.commit()
    conn.close()
    return str(db_path)


@pytest.mark.asyncio
async def test_database_scan_reports_pii_column_with_confidence(
    client: AsyncClient, sqlite_db_path: str
) -> None:
    await signup(client)
    project = await create_project(client)

    resp = await client.post(
        "/api/v1/database-scan",
        json={
            "project_id": project["id"],
            "engine": "sqlite",
            "connection_string": sqlite_db_path,
            "table_name": "customers",
            "sample_rows": 50,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["rows_sampled"] == 3
    email_column = next(c for c in body["columns"] if c["column"] == "email")
    assert email_column["category"] == "contact"
    assert email_column["confidence"] > 0
    # The "notes" column has no PII shape in any sampled row, so it never appears.
    assert all(c["column"] != "notes" for c in body["columns"])


@pytest.mark.asyncio
async def test_database_scan_never_persists_the_connection_string(
    client: AsyncClient, sqlite_db_path: str
) -> None:
    await signup(client)
    project = await create_project(client)

    resp = await client.post(
        "/api/v1/database-scan",
        json={
            "project_id": project["id"],
            "engine": "sqlite",
            "connection_string": sqlite_db_path,
            "table_name": "customers",
            "sample_rows": 50,
        },
    )
    assert resp.status_code == 200, resp.text

    audit = await client.get("/api/v1/audit", params={"limit": 50})
    assert sqlite_db_path not in audit.text


@pytest.mark.asyncio
async def test_database_scan_bad_connection_fails_predictably(client: AsyncClient) -> None:
    await signup(client)
    project = await create_project(client)

    resp = await client.post(
        "/api/v1/database-scan",
        json={
            "project_id": project["id"],
            "engine": "sqlite",
            "connection_string": "/nonexistent/path/does-not-exist.db",
            "table_name": "customers",
            "sample_rows": 50,
        },
    )
    # A missing table against a fresh sqlite file is a clean, structured failure, not a
    # silently-empty result or an unhandled 500.
    assert resp.status_code in (400, 422)
    assert "error" in resp.json()
