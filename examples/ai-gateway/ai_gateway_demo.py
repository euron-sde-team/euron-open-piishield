"""The AI gateway round trip: protect, call a model, restore, with no real API key needed.

This example runs standalone, with a stub PIIShield transport and a stub "external model"
call, so it demonstrates the protect/restore contract without a running PIIShield API or
a real model API key. To see the same flow against a real backend, drop the
``StubTransport`` and construct ``PIIShield(api_url=..., api_key=..., project_id=...)`` as
usual; every line below that calls ``shield.protect`` / ``shield.restore`` stays the same.

    python ai_gateway_demo.py

The point this example proves: the text sent to ``call_external_model`` (the stand-in for
a real AI provider) never contains the real PAN, and ``scope_id`` (the reference that
makes restoration possible, matching the real API's
``ai_gateway.schemas.GatewayProtectOut``) is never part of that text either, exactly the
separation the README's "AI gateway safety property" section describes.
"""

from __future__ import annotations

import re
import sys
import uuid
from typing import Any

import httpx

from euron_piishield import PIIShield


class StubTransport(httpx.BaseTransport):
    """A fake PIIShield API: masks a PAN pattern with a tokenize placeholder and keeps
    the mapping in memory, exactly like the real vault would, for this example's protect
    and restore calls only."""

    PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")

    def __init__(self) -> None:
        self._vault: dict[str, dict[str, str]] = {}

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        import json

        body: dict[str, Any] = json.loads(request.content) if request.content else {}
        path = request.url.path

        if path == "/api/v1/ai-gateway/protect":
            prompt = str(body["prompt"])
            mapping: dict[str, str] = {}
            counter = 0

            def replace(match: re.Match[str]) -> str:
                nonlocal counter
                counter += 1
                placeholder = f"[PAN_{counter:03d}]"
                mapping[placeholder] = match.group(0)
                return placeholder

            protected_prompt = self.PAN_RE.sub(replace, prompt)
            scope_id = f"scope_{uuid.uuid4().hex[:12]}"
            self._vault[scope_id] = mapping
            return httpx.Response(
                200,
                json={
                    "protected_prompt": protected_prompt,
                    "scope_id": scope_id,
                    "findings": [
                        {
                            "category": "pan",
                            "start": 0,
                            "end": 0,
                            "confidence": 0.95,
                            "checksum_valid": None,
                            "recognizer": "pan_entity_pattern",
                            "method": "tokenize",
                            "placeholder": next(iter(mapping), None),
                            "in_review": False,
                        }
                    ],
                },
            )

        if path == "/api/v1/ai-gateway/restore":
            scope_id = str(body["scope_id"])
            text = str(body["model_response"])
            mapping = self._vault.get(scope_id, {})
            restored = 0
            for placeholder, original in mapping.items():
                if placeholder in text:
                    text = text.replace(placeholder, original)
                    restored += 1
            return httpx.Response(200, json={"restored_response": text, "placeholders_restored": restored})

        return httpx.Response(404, json={"error": {"code": "not_found", "message": path}})


def call_external_model(protected_prompt: str) -> str:
    """Stands in for a real AI provider call. It only ever sees the protected text, and
    its "response" below only ever echoes that same protected text back, demonstrating
    that no real PAN crosses this boundary in either direction."""
    print(f"  -> sending to external model: {protected_prompt!r}")
    response = f"Based on the record, {protected_prompt.split('is ')[1]}"
    print(f"  <- external model responded: {response!r}")
    return response


def main() -> int:
    http_client = httpx.Client(transport=StubTransport(), base_url="http://stub.local")
    shield = PIIShield(
        api_url="http://stub.local", api_key="stub-key", project_id="stub-project", http_client=http_client
    )

    prompt = "My PAN is ABCDE1234F. Explain my tax record."
    print(f"Original prompt: {prompt!r}\n")

    protected = shield.protect(prompt)
    print(f"Protected text (safe to send to a model): {protected.protected_text!r}")
    print(f"Scope id (keep server side only):         {protected.scope_id!r}\n")

    assert "ABCDE1234F" not in protected.protected_text, "the real PAN must never reach the model"

    model_response = call_external_model(protected.protected_text)
    print()

    restored = shield.restore(protected.scope_id, model_response)
    print(f"Restored text (for the calling application only): {restored.restored_text!r}")

    shield.close()
    return 0 if "ABCDE1234F" in restored.restored_text else 1


if __name__ == "__main__":
    sys.exit(main())
