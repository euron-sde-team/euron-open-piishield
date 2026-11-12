"""A tiny mock LLM HTTP service for the demo seed and tests.

It receives a (already gateway-protected) prompt and echoes back a response that
deliberately repeats the placeholders it was given, as a real model might when asked to
"confirm the customer's email and card on file": this gives the AI gateway's restore flow
something real to resolve in the demo and in tests, so the round trip is genuine instead
of a hand-inserted row (per the task brief: "so traces of real protect/restore round trips
exist, not hand-inserted rows, wherever practical").

Never does its own PII detection; it just proves the gateway boundary: this service never
receives an original value (only placeholders), so it cannot leak one even if its own
logs were public, which is the point of the whole AI privacy gateway.
"""

from __future__ import annotations

import re

from fastapi import FastAPI
from pydantic import BaseModel

_PLACEHOLDER = re.compile(r"\[[A-Z_]+_\d{3}\]")


class CompletionIn(BaseModel):
    prompt: str


class CompletionOut(BaseModel):
    response: str


def create_mock_ai_app() -> FastAPI:
    app = FastAPI(title="PIIShield Mock AI", version="0.1.0")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/complete", response_model=CompletionOut)
    async def complete(body: CompletionIn) -> CompletionOut:
        placeholders = _PLACEHOLDER.findall(body.prompt)
        if placeholders:
            confirmed = ", ".join(sorted(set(placeholders)))
            response = f"Thanks, I have noted the details for {confirmed}. Is there anything else?"
        else:
            response = "Thanks, noted. Is there anything else?"
        return CompletionOut(response=response)

    return app


# ``uvicorn mockai.app:app`` (see infra/docker/server.Dockerfile and
# deploy/compose/compose.yaml's mockai service) needs a module-level ASGI app, not only
# the factory above; tests and the demo seed may use either.
app = create_mock_ai_app()
