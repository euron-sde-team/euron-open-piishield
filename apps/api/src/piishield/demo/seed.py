"""Demo data: Verdant Pay, a fictional fintech processing customer payments and KYC
documents, so screenshots and e2e have real data instead of empty tables.

Seeds, through the real HTTP API (not direct database writes, so the seeded data is
exactly what a real client would produce and the AI gateway round trip is genuine):
* an organization, owner (vault access), and a second project.
* a policy marking "financial" and "government_id" required, confidence threshold 0.6.
* a few scans of realistic-but-fake PII text: some tokenized (vault entries created),
  some redacted.
* a couple of low-confidence findings left in the review queue.
* one document scan (a small generated PDF with an embedded card number).
* one AI gateway protect/restore round trip through the mock AI service.

No real person's data is used anywhere; every value below is fabricated for this demo.
"""

from __future__ import annotations

import asyncio
import os

import httpx

DEMO_PASSWORD = os.environ.get("PIISHIELD_DEMO_PASSWORD", "Demo-Owner-Pass-1")
API_URL = os.environ.get("PIISHIELD_API_URL", "http://localhost:8080")
MOCK_AI_URL = os.environ.get("MOCK_AI_URL", "http://localhost:5550")

OWNER_EMAIL = "priya.nair@verdantpay.example"
ORG_NAME = "Verdant Pay"


async def run() -> None:
    async with httpx.AsyncClient(base_url=API_URL, timeout=30.0) as client:
        await _seed(client)


async def _signup_or_login(client: httpx.AsyncClient) -> dict[str, object]:
    resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "org_name": ORG_NAME,
            "name": "Priya Nair",
            "email": OWNER_EMAIL,
            "password": DEMO_PASSWORD,
        },
    )
    if resp.status_code == 201:
        data: dict[str, object] = resp.json()
        return data
    resp = await client.post(
        "/api/v1/auth/login", json={"email": OWNER_EMAIL, "password": DEMO_PASSWORD}
    )
    resp.raise_for_status()
    data = resp.json()
    return data


async def _seed(client: httpx.AsyncClient) -> None:
    session = await _signup_or_login(client)
    token = session["token"]
    client.headers["Authorization"] = f"Bearer {token}"

    projects = (await client.get("/api/v1/projects")).json()
    project = next((p for p in projects if p["slug"] == "customer-support"), None)
    if project is None:
        resp = await client.post(
            "/api/v1/projects",
            json={
                "name": "Customer Support",
                "slug": "customer-support",
                "description": "Support tickets and KYC documents from Verdant Pay's merchant onboarding flow.",
            },
        )
        resp.raise_for_status()
        project = resp.json()
    project_id = project["id"]

    await client.put(
        f"/api/v1/projects/{project_id}/policy",
        json={
            "required_categories": ["financial", "government_id"],
            "masking_method": {
                "financial": "tokenize",
                "government_id": "redact",
                "contact": "partial_mask",
            },
            "partial_mask_reveal": 4,
            "confidence_threshold": 0.6,
            "retention_days": 90,
        },
    )

    # A support ticket with tokenized financial/contact data.
    ticket_text = (
        "Customer Ananya Gupta (ananya.gupta@verdantpay.example, +91 98765 43210) reports her "
        "payment of card 4539148803436467 did not settle. Her linked bank account is "
        "000123456789 at IFSC HDFC0001234. PAN on file: ABCPD1234E."
    )
    await client.post(
        "/api/v1/protect/text",
        json={"project_id": project_id, "text": ticket_text, "scope_id": "demo-ticket-1021"},
    )

    # A KYC note with a redacted Aadhaar number (checksum-valid, confidence 0.95) and a
    # passport number pattern (0.5, below the 0.6 default threshold) left for review.
    kyc_text = (
        "Applicant Rohan Verma submitted Aadhaar 234123412346 and passport Z1234567 for "
        "merchant verification. Address on file: 221 MG Road, Pune 411001."
    )
    await client.post(
        "/api/v1/protect/text",
        json={"project_id": project_id, "text": kyc_text, "scope_id": "demo-kyc-77"},
    )

    # A clearly credential-bearing log line, tokenized, to populate the vault further.
    log_text = "Deploy failed: api_key=sk-live-demoFAKEkey1234567890abcdefghijklmno for service billing-worker"
    await client.post(
        "/api/v1/protect/text",
        json={"project_id": project_id, "text": log_text, "scope_id": "demo-log-9"},
    )

    # AI gateway: a real protect -> mock model call -> restore round trip (AC9).
    prompt = "Please confirm the refund for ananya.gupta@verdantpay.example, card 4539148803436467."
    protect_resp = await client.post(
        "/api/v1/ai-gateway/protect",
        json={"project_id": project_id, "prompt": prompt, "scope_id": "demo-gateway-refund-1"},
    )
    protect_resp.raise_for_status()
    protected = protect_resp.json()

    async with httpx.AsyncClient(base_url=MOCK_AI_URL, timeout=15.0) as ai_client:
        completion = await ai_client.post(
            "/v1/complete", json={"prompt": protected["protected_prompt"]}
        )
        completion.raise_for_status()
        model_response = completion.json()["response"]

    await client.post(
        "/api/v1/ai-gateway/restore",
        json={
            "project_id": project_id,
            "scope_id": protected["scope_id"],
            "model_response": model_response,
        },
    )

    await _seed_document_scan(client, project_id)

    print(f"seeded {ORG_NAME}")
    print(f"login: {OWNER_EMAIL} / {DEMO_PASSWORD}")


async def _seed_document_scan(client: httpx.AsyncClient, project_id: str) -> None:
    """A tiny generated PDF with an embedded card number and email, so AC8 (document
    scan/protect) has a real, non-empty report in the demo (PLAN.md: "at least one
    document scan result")."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72),
        "Verdant Pay merchant onboarding note.\n"
        "Contact: finance@verdantpay.example\n"
        "Card on file: 4539148803436467",
    )
    pdf_bytes = doc.tobytes()
    doc.close()

    files = {"file": ("onboarding-note.pdf", pdf_bytes, "application/pdf")}
    resp = await client.post(f"/api/v1/documents?project_id={project_id}", files=files)
    resp.raise_for_status()


if __name__ == "__main__":
    asyncio.run(run())
