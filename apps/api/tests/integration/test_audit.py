"""AC11: the audit log records every scan/mask/redact/tokenize/detokenize call (who,
when, finding counts, categories) but never the original sensitive value or a vault
mapping's plaintext.

The scanner test below mirrors the sibling AgentGuard project's own "secret values never
reach the logs" pattern: seed real-looking fake PII, exercise every PII-touching
endpoint, then grep the ENTIRE audit log response body (every field, not just the ones we
expect to be safe) for each literal secret value."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.helpers import create_project, set_policy, signup

pytestmark = pytest.mark.integration

_SECRET_EMAIL = "ananya.gupta.secret@example.com"
_SECRET_CARD = "4539148803436467"
_SECRET_AADHAAR = "234123412346"
_SECRET_API_KEY = "sk-live-veryrealsecretvalueabcdefghijklmno"


@pytest.mark.asyncio
async def test_ac11_audit_log_never_contains_a_real_value(client: AsyncClient) -> None:
    await signup(client)
    project = await create_project(client)
    await set_policy(
        client,
        project["id"],
        required=["financial", "government_id"],
        masking_method={
            "financial": "tokenize",
            "government_id": "redact",
            "credential": "tokenize",
        },
    )

    await client.post(
        "/api/v1/protect/text",
        json={
            "project_id": project["id"],
            "text": (
                f"Customer email {_SECRET_EMAIL}, card {_SECRET_CARD}, "
                f"Aadhaar {_SECRET_AADHAAR}, api_key={_SECRET_API_KEY}"
            ),
            "scope_id": "ac11-scope",
        },
    )

    # Detokenize one of the tokenized values so a "detokenize" audit action exists too.
    scan = await client.get("/api/v1/review", params={"project_id": project["id"]})
    assert scan.status_code == 200

    protect_again = await client.post(
        "/api/v1/protect/text",
        json={
            "project_id": project["id"],
            "text": f"card {_SECRET_CARD} again",
            "scope_id": "ac11-scope",
        },
    )
    placeholder = next(
        f["placeholder"] for f in protect_again.json()["findings"] if f["placeholder"]
    )
    await client.post(
        "/api/v1/vault/detokenize",
        json={"project_id": project["id"], "scope_id": "ac11-scope", "placeholder": placeholder},
    )

    audit = await client.get("/api/v1/audit", params={"limit": 200})
    assert audit.status_code == 200, audit.text
    raw = audit.text

    for secret in (_SECRET_EMAIL, _SECRET_CARD, _SECRET_AADHAAR, _SECRET_API_KEY):
        assert secret not in raw, f"secret value leaked into the audit log response: {secret}"

    body = audit.json()
    actions = {e["action"] for e in body["items"]}
    assert "scan" in actions
    assert "detokenize" in actions

    # Categories are category labels, never the matched text.
    for entry in body["items"]:
        for category in entry["categories"]:
            assert category in {
                "financial",
                "government_id",
                "contact",
                "personal",
                "credential",
            }


@pytest.mark.asyncio
async def test_ac11_audit_details_never_echo_a_password_or_token_field(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Even a caller-controlled field name like ``password`` passed into audit details is
    dropped by ``_sanitize_details``, not merely by convention of what callers happen to
    pass today."""
    import uuid as _uuid

    from piishield.audit.service import Actor, record

    actor = Actor(_uuid.uuid4(), _uuid.uuid4(), "test@example.com", "owner")
    entry = record(
        session,
        actor,
        "test.action",
        password="should-never-survive",
        secret="also-should-never-survive",
        safe_count=3,
    )
    assert "password" not in entry.details
    assert "secret" not in entry.details
    assert entry.details["safe_count"] == 3
