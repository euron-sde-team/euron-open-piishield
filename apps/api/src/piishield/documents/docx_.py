"""DOCX scanning and protection via python-docx.

Every paragraph (document body, and table cells) is scanned and protected as one leaf of
text; the module rewrites each run's text in place so formatting (bold, italic, existing
runs) is preserved as well as python-docx allows, and the file stays a valid .docx (a ZIP
of OOXML parts), never a plaintext dump.
"""

from __future__ import annotations

import io
from collections.abc import Awaitable, Callable

from docx import Document

from piishield.detectors.recognizers import Finding
from piishield.documents.exceptions import DocumentParseError

ProtectText = Callable[[str], Awaitable[tuple[str, list[Finding]]]]


async def protect_docx(
    data: bytes, protect_text: ProtectText
) -> tuple[bytes, list[dict[str, object]]]:
    try:
        document = Document(io.BytesIO(data))
    except Exception as exc:
        raise DocumentParseError(str(exc)) from exc

    categories_seen: set[str] = set()
    finding_count = 0

    async def _protect_paragraph(paragraph: object) -> None:
        nonlocal finding_count
        text = "".join(run.text for run in paragraph.runs)  # type: ignore[attr-defined]
        if not text.strip():
            return
        protected, findings = await protect_text(text)
        if not findings or protected == text:
            return
        finding_count += len(findings)
        categories_seen.update(f.category for f in findings)
        # Collapse into the first run and clear the rest: simplest way to keep the file
        # valid without trying to re-split the protected text across the original run
        # boundaries (which carried no PII-relevant formatting of their own in practice).
        runs = paragraph.runs  # type: ignore[attr-defined]
        if runs:
            runs[0].text = protected
            for run in runs[1:]:
                run.text = ""

    for paragraph in document.paragraphs:
        await _protect_paragraph(paragraph)
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    await _protect_paragraph(paragraph)

    out = io.BytesIO()
    document.save(out)
    breakdown: list[dict[str, object]] = (
        [{"finding_count": finding_count, "categories": sorted(categories_seen)}]
        if finding_count
        else []
    )
    return out.getvalue(), breakdown
