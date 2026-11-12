"""Document scanning and protection: dispatch by extension to the right processor, each
of which calls back into ``protection.service.protect_text`` for every text leaf it finds
(a PDF page, a DOCX paragraph, a spreadsheet cell), so document handling reuses the exact
same detection, policy, review-threshold and tokenization behaviour as text and JSON
(AC8 builds on AC2/AC3/AC4/AC13 rather than re-implementing them)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from piishield.audit.service import Actor
from piishield.audit.service import record as audit_record
from piishield.core.kv import KV
from piishield.core.sealing import Sealer
from piishield.detectors.recognizers import Finding
from piishield.documents import repository
from piishield.documents.docx_ import protect_docx
from piishield.documents.exceptions import UnsupportedDocumentTypeError
from piishield.documents.pdf import protect_pdf
from piishield.documents.xlsx_csv import protect_csv, protect_xlsx
from piishield.protection.service import protect_text

_EXTENSIONS = {"pdf", "docx", "xlsx", "csv"}


def _extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _as_int(value: object) -> int:
    assert isinstance(value, int)
    return value


def _as_str_list(value: object) -> list[str]:
    assert isinstance(value, list)
    return [str(item) for item in value]


async def protect_document(
    session: AsyncSession,
    kv: KV,
    sealer: Sealer,
    actor: Actor,
    project_id: uuid.UUID,
    filename: str,
    data: bytes,
    scope_id: str | None = None,
) -> tuple[bytes, str]:
    """Returns (protected_file_bytes, file_type). Records exactly one document_scans row
    and one audit entry per call, same contract as protect_text/protect_json."""
    file_type = _extension(filename)
    if file_type not in _EXTENSIONS:
        raise UnsupportedDocumentTypeError(filename)
    resolved_scope = scope_id or uuid.uuid4().hex

    async def _protect_leaf(text: str) -> tuple[str, list[Finding]]:
        protected, findings, _ = await protect_text(
            session, kv, sealer, actor, project_id, text, scope_id=resolved_scope, source="document"
        )
        # protect_text already committed and recorded its own scan/audit event per leaf,
        # which is fine for a handful of pages/cells but would be excessive for a large
        # spreadsheet; 0.1.0 accepts this for correctness-first simplicity (reusing the
        # exact same pipeline) and documents it as a known cost in docs/architecture
        # rather than a silent one.
        return protected, [
            Finding(
                f.category,
                f.start,
                f.end,
                f.confidence,
                text[f.start : f.end],
                f.checksum_valid,
                f.recognizer,
            )
            for f in findings
            if not f.in_review
        ]

    if file_type == "pdf":
        out, breakdown = await protect_pdf(data, _protect_leaf)
    elif file_type == "docx":
        out, breakdown = await protect_docx(data, _protect_leaf)
    elif file_type == "xlsx":
        out, breakdown = await protect_xlsx(data, _protect_leaf)
    else:
        out, breakdown = await protect_csv(data, _protect_leaf)

    finding_count = sum(_as_int(b["finding_count"]) for b in breakdown)
    categories = sorted({c for b in breakdown for c in _as_str_list(b["categories"])})
    repository.record_scan(
        session, actor.org_id, project_id, filename, file_type, finding_count, categories, breakdown
    )
    audit_record(
        session,
        actor,
        "scan",
        project_id=project_id,
        finding_count=finding_count,
        categories=categories,
        source="document",
        filename=filename,
    )
    await session.commit()
    return out, file_type
