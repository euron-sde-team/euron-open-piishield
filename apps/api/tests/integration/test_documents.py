"""AC8: PDF, DOCX and XLSX/CSV uploads return a protected version of the SAME file
format (not a plaintext dump), with detected values masked/redacted/tokenized, and the
scan is reported by page or sheet via the audit/report trail (the response itself is the
binary file; ``scan_repo`` records the breakdown)."""

from __future__ import annotations

import csv
import io

import pytest
from httpx import AsyncClient

from tests.integration.helpers import create_project, set_policy, signup

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_ac8_pdf_round_trip_keeps_pdf_format_and_masks_value(client: AsyncClient) -> None:
    import fitz

    await signup(client)
    project = await create_project(client)
    await set_policy(
        client, project["id"], masking_method={"contact": "redact", "financial": "redact"}
    )

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Contact: jane@example.com\nCard: 4539148803436467")
    pdf_bytes = doc.tobytes()
    doc.close()

    resp = await client.post(
        f"/api/v1/documents?project_id={project['id']}",
        files={"file": ("note.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    out_bytes = resp.content

    # Still a valid, openable PDF (not a plaintext dump). PyMuPDF's own redaction
    # (add_redact_annot + apply_redactions) genuinely removes the underlying text rather
    # than overlaying a "[REDACTED:...]" marker string, so the proof here is that neither
    # original value is anywhere in the extracted text layer any more: a black box
    # redaction, not a plaintext replacement.
    out_doc = fitz.open(stream=out_bytes, filetype="pdf")
    text = out_doc[0].get_text()
    out_doc.close()
    assert "jane@example.com" not in text
    assert "4539148803436467" not in text


@pytest.mark.asyncio
async def test_ac8_docx_round_trip_keeps_docx_format(client: AsyncClient) -> None:
    import docx

    await signup(client)
    project = await create_project(client)
    await set_policy(client, project["id"], masking_method={"contact": "redact"})

    doc = docx.Document()
    doc.add_paragraph("Please reach jane@example.com for follow up.")
    buf = io.BytesIO()
    doc.save(buf)
    docx_bytes = buf.getvalue()

    resp = await client.post(
        f"/api/v1/documents?project_id={project['id']}",
        files={
            "file": (
                "note.docx",
                docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert resp.status_code == 200, resp.text
    assert "wordprocessingml" in resp.headers["content-type"]

    out_doc = docx.Document(io.BytesIO(resp.content))
    full_text = "\n".join(p.text for p in out_doc.paragraphs)
    assert "jane@example.com" not in full_text
    assert "[REDACTED" in full_text


@pytest.mark.asyncio
async def test_ac8_xlsx_round_trip_keeps_xlsx_format(client: AsyncClient) -> None:
    import openpyxl

    await signup(client)
    project = await create_project(client)
    await set_policy(client, project["id"], masking_method={"contact": "redact"})

    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "email"
    ws["A2"] = "jane@example.com"
    buf = io.BytesIO()
    wb.save(buf)
    xlsx_bytes = buf.getvalue()

    resp = await client.post(
        f"/api/v1/documents?project_id={project['id']}",
        files={
            "file": (
                "sheet.xlsx",
                xlsx_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 200, resp.text
    assert "spreadsheetml" in resp.headers["content-type"]

    out_wb = openpyxl.load_workbook(io.BytesIO(resp.content))
    out_ws = out_wb.active
    assert out_ws is not None
    assert out_ws["A2"].value != "jane@example.com"
    assert "[REDACTED" in str(out_ws["A2"].value)


@pytest.mark.asyncio
async def test_ac8_csv_round_trip_keeps_csv_format(client: AsyncClient) -> None:
    await signup(client)
    project = await create_project(client)
    await set_policy(client, project["id"], masking_method={"contact": "redact"})

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["name", "email"])
    writer.writerow(["Jane", "jane@example.com"])
    csv_bytes = buf.getvalue().encode()

    resp = await client.post(
        f"/api/v1/documents?project_id={project['id']}",
        files={"file": ("rows.csv", csv_bytes, "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/csv")

    out_text = resp.content.decode()
    rows = list(csv.reader(io.StringIO(out_text)))
    assert rows[0] == ["name", "email"]
    assert rows[1][0] == "Jane"
    assert "jane@example.com" not in out_text
    assert "[REDACTED" in rows[1][1]
