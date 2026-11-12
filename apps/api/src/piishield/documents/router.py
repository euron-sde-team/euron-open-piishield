"""Document upload, scan and protect."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, UploadFile
from fastapi.responses import Response

from piishield.auth.dependencies import StaffWrite
from piishield.core.deps import ContainerDep, SessionDep
from piishield.documents import service

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

_CONTENT_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
}


@router.post("", summary="Upload and protect a document (PDF, DOCX, XLSX or CSV)")
async def protect_document(
    project_id: uuid.UUID,
    file: UploadFile,
    actor: StaffWrite,
    container: ContainerDep,
    session: SessionDep,
) -> Response:
    data = await file.read()
    out, file_type = await service.protect_document(
        session, container.kv, container.sealer, actor, project_id, file.filename or "upload", data
    )
    return Response(
        content=out,
        media_type=_CONTENT_TYPES[file_type],
        headers={"content-disposition": f'attachment; filename="protected_{file.filename}"'},
    )
