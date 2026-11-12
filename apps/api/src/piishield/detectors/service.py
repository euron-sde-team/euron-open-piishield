"""Scanning: runs the built-in recognizers plus a project's enabled custom patterns."""

from __future__ import annotations

import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from piishield.audit.service import Actor, record
from piishield.core.db import OrgScope
from piishield.core.metrics import FINDINGS, SCANS
from piishield.detectors import repository
from piishield.detectors.exceptions import InvalidPatternError, RecognizerNotFoundError
from piishield.detectors.models import CustomRecognizer
from piishield.detectors.recognizers import RECOGNIZERS, Finding, Recognizer, scan_text
from piishield.projects.service import ensure_project


async def recognizers_for_project(
    session: AsyncSession, scope: OrgScope, project_id: uuid.UUID
) -> list[Recognizer]:
    custom = await repository.list_for_project(session, scope, project_id)
    extra: list[Recognizer] = []
    for row in custom:
        try:
            pattern = re.compile(row.pattern)
        except re.error:
            continue  # a pattern that stopped compiling after being saved is skipped, not fatal
        extra.append(Recognizer(row.name, row.category, pattern, row.confidence))
    return [*RECOGNIZERS, *extra]


async def scan(
    session: AsyncSession, scope: OrgScope, project_id: uuid.UUID, text: str
) -> list[Finding]:
    await ensure_project(session, scope, project_id)
    recognizers = await recognizers_for_project(session, scope, project_id)
    findings = scan_text(text, recognizers)
    SCANS.labels(source="detectors_scan").inc()
    for f in findings:
        FINDINGS.labels(category=f.category).inc()
    return findings


async def create_custom_recognizer(
    session: AsyncSession,
    actor: Actor,
    project_id: uuid.UUID,
    name: str,
    category: str,
    pattern: str,
    confidence: float,
) -> CustomRecognizer:
    await ensure_project(session, actor.scope, project_id)
    try:
        re.compile(pattern)
    except re.error as exc:
        raise InvalidPatternError(pattern, str(exc)) from exc
    row = CustomRecognizer(
        org_id=actor.org_id,
        project_id=project_id,
        name=name,
        category=category,
        pattern=pattern,
        confidence=confidence,
    )
    repository.add(session, row)
    await session.flush()
    record(
        session, actor, "recognizer.created", project_id=project_id, name=name, category=category
    )
    await session.commit()
    return row


async def list_custom_recognizers(
    session: AsyncSession, scope: OrgScope, project_id: uuid.UUID
) -> list[CustomRecognizer]:
    return await repository.list_for_project(session, scope, project_id)


async def delete_custom_recognizer(
    session: AsyncSession, actor: Actor, recognizer_id: uuid.UUID
) -> None:
    row = await repository.get(session, actor.scope, recognizer_id)
    if row is None:
        raise RecognizerNotFoundError()
    row.enabled = False
    record(session, actor, "recognizer.disabled", project_id=row.project_id, name=row.name)
    await session.commit()
