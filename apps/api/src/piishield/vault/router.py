"""Detokenization (vault-access gated, AC5) and vault access grant management (owner
only: granting vault access is itself a sensitive admin action)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from piishield.auth.dependencies import OrgOwner, VaultAccess
from piishield.core.deps import ContainerDep, SessionDep
from piishield.vault import service
from piishield.vault.models import VaultGrant
from piishield.vault.schemas import DetokenizeIn, DetokenizeOut, VaultGrantIn, VaultGrantOut

router = APIRouter(prefix="/api/v1/vault", tags=["vault"])


@router.post(
    "/detokenize",
    response_model=DetokenizeOut,
    summary="Resolve a placeholder to its original value",
)
async def detokenize(
    body: DetokenizeIn, actor: VaultAccess, container: ContainerDep, session: SessionDep
) -> DetokenizeOut:
    value, category = await service.detokenize(
        session, container.sealer, actor, body.project_id, body.scope_id, body.placeholder
    )
    return DetokenizeOut(placeholder=body.placeholder, value=value, category=category)


def _grant_out(g: VaultGrant) -> VaultGrantOut:
    return VaultGrantOut(
        id=g.id, user_id=g.user_id, api_key_id=g.api_key_id, revoked_at=g.revoked_at
    )


@router.post("/grants", response_model=VaultGrantOut, status_code=201, summary="Grant vault access")
async def create_grant(body: VaultGrantIn, actor: OrgOwner, session: SessionDep) -> VaultGrantOut:
    return _grant_out(await service.grant_access(session, actor, body.user_id, body.api_key_id))


@router.get(
    "/grants", response_model=list[VaultGrantOut], summary="List active vault access grants"
)
async def list_grants(actor: OrgOwner, session: SessionDep) -> list[VaultGrantOut]:
    rows = await service.list_grants(session, actor.scope)
    return [_grant_out(r) for r in rows]


@router.delete("/grants/{grant_id}", status_code=204, summary="Revoke a vault access grant")
async def revoke_grant(grant_id: uuid.UUID, actor: OrgOwner, session: SessionDep) -> None:
    await service.revoke_grant(session, actor, grant_id)
