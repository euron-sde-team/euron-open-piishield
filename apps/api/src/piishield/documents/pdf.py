"""PDF text-layer scanning and protection via PyMuPDF (fitz).

0.1.0 only reads and rewrites the text layer (PLAN.md: "PDF (text layer)"); a scanned
image PDF with no extractable text yields zero findings and is returned unchanged, which
is the documented 0.1.0 boundary (image OCR is roadmap). Redaction uses PyMuPDF's own
``add_redact_annot`` + ``apply_redactions``, which removes the underlying text (not only a
visual overlay), so a redacted PDF cannot be searched or copy-pasted back to the original.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import pymupdf as fitz

from piishield.detectors.recognizers import Finding
from piishield.documents.exceptions import DocumentParseError

ProtectPage = Callable[[str], Awaitable[tuple[str, list[Finding]]]]


async def protect_pdf(
    data: bytes, protect_page: ProtectPage
) -> tuple[bytes, list[dict[str, object]]]:
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise DocumentParseError(str(exc)) from exc

    breakdown: list[dict[str, object]] = []
    try:
        for page_index in range(doc.page_count):
            page = doc[page_index]
            text = page.get_text()
            if not text.strip():
                continue
            _protected_text, findings = await protect_page(text)
            if not findings:
                continue
            categories = sorted({f.category for f in findings})
            breakdown.append(
                {"page": page_index + 1, "finding_count": len(findings), "categories": categories}
            )
            # Redact every finding's matched span at the page level: PyMuPDF redaction
            # works on rectangles, found by re-searching for the exact matched text (the
            # page's own text extraction order matches what detectors scanned).
            for finding in findings:
                needle = text[finding.start : finding.end]
                for rect in page.search_for(needle):
                    page.add_redact_annot(rect, fill=(0, 0, 0))
            page.apply_redactions()
        out = doc.tobytes(garbage=4, deflate=True)
    finally:
        doc.close()
    return out, breakdown
