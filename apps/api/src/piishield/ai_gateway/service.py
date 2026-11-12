"""The AI privacy gateway: protect a prompt before it reaches an external model, and
restore placeholders in the model's response for the calling application only (AC9).

Trust boundary, spelled out because it is easy to get wrong: ``restore`` is NOT the same
operation as ``vault.detokenize`` and is not gated by ``VaultAccess`` (AC5's dedicated
vault permission). The gateway's caller is the application that itself just called
``protect`` and received ``scope_id`` back; restoring is completing that same round trip,
not a new act of reaching into someone else's vault entries. Scope isolation is what keeps
this safe: ``restore`` only ever resolves placeholders that exist under the exact
``(org, project, scope_id)`` the caller supplies, and a scope_id is an opaque, unguessable
token the caller already had to possess to get this far (AC6: it is never embedded in the
protected prompt sent to the model, only returned once in the protect response to the
calling application). A caller who does not already know a valid scope_id learns nothing
by guessing: a wrong scope_id simply resolves no placeholders.
"""

from __future__ import annotations

import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from piishield.ai_gateway import repository
from piishield.audit.service import Actor
from piishield.audit.service import record as audit_record
from piishield.core.db import OrgScope
from piishield.core.kv import KV
from piishield.core.sealing import Sealer
from piishield.projects.service import ensure_project
from piishield.protection.service import ProtectedFinding, protect_text
from piishield.vault.service import resolve_in_scope

_PLACEHOLDER = re.compile(r"\[[A-Z_]+_\d{3}\]")


async def protect(
    session: AsyncSession,
    kv: KV,
    sealer: Sealer,
    actor: Actor,
    project_id: uuid.UUID,
    prompt: str,
    scope_id: str | None,
) -> tuple[str, list[ProtectedFinding], str]:
    """Always tokenizes (never redacts/masks) findings that are not sitting in review,
    so the exact value can be restored later for the calling application; a finding
    below the confidence threshold still goes to the review queue and is left
    unprotected in the prompt, same as any other protect call."""
    protected, findings, resolved_scope = await protect_text(
        session,
        kv,
        sealer,
        actor,
        project_id,
        prompt,
        method_overrides={
            "financial": "tokenize",
            "government_id": "tokenize",
            "contact": "tokenize",
            "personal": "tokenize",
            "credential": "tokenize",
        },
        scope_id=scope_id,
        source="ai_gateway_protect",
    )
    repository.record_call(
        session,
        actor.org_id,
        project_id,
        resolved_scope,
        "protect",
        len(findings),
        [f.category for f in findings],
    )
    audit_record(
        session,
        actor,
        "ai_gateway.protect",
        project_id=project_id,
        finding_count=len(findings),
        categories=[f.category for f in findings],
        scope_id=resolved_scope,
    )
    await session.commit()
    return protected, findings, resolved_scope


async def restore(
    session: AsyncSession,
    sealer: Sealer,
    scope: OrgScope,
    actor: Actor,
    project_id: uuid.UUID,
    scope_id: str,
    model_response: str,
) -> tuple[str, int]:
    """Replaces every placeholder found in ``model_response`` that resolves within this
    exact scope; anything else (a placeholder-looking string from another scope, or no
    placeholders at all) is left untouched, never an error, since the model's own text may
    legitimately contain bracketed text that merely looks like a placeholder."""
    await ensure_project(session, scope, project_id)
    restored = model_response
    count = 0
    categories: list[str] = []
    for match in set(_PLACEHOLDER.findall(model_response)):
        resolved = await resolve_in_scope(session, sealer, scope, project_id, scope_id, match)
        if resolved is None:
            continue
        value, category = resolved
        restored = restored.replace(match, value)
        count += 1
        categories.append(category)
    repository.record_call(
        session, actor.org_id, project_id, scope_id, "restore", count, categories
    )
    audit_record(
        session,
        actor,
        "ai_gateway.restore",
        project_id=project_id,
        finding_count=count,
        categories=categories,
        scope_id=scope_id,
    )
    await session.commit()
    return restored, count
