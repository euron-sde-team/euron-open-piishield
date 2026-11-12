"""XLSX and CSV scanning and protection via openpyxl and the standard csv module.

Every cell value that is a string is scanned and protected independently; numbers, dates
and formulas pass through untouched (consistent with the JSON leaf-recursion rule: only
string leaves are ever candidates). The output stays a real workbook or a real CSV file,
never a plaintext dump of the findings.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Awaitable, Callable

from openpyxl import load_workbook

from piishield.detectors.recognizers import Finding
from piishield.documents.exceptions import DocumentParseError

ProtectText = Callable[[str], Awaitable[tuple[str, list[Finding]]]]


async def protect_xlsx(
    data: bytes, protect_text: ProtectText
) -> tuple[bytes, list[dict[str, object]]]:
    try:
        workbook = load_workbook(io.BytesIO(data))
    except Exception as exc:
        raise DocumentParseError(str(exc)) from exc

    breakdown: list[dict[str, object]] = []
    for sheet in workbook.worksheets:
        finding_count = 0
        categories_seen: set[str] = set()
        for row in sheet.iter_rows():
            for cell in row:
                if not isinstance(cell.value, str) or not cell.value.strip():
                    continue
                protected, findings = await protect_text(cell.value)
                if not findings:
                    continue
                finding_count += len(findings)
                categories_seen.update(f.category for f in findings)
                cell.value = protected
        if finding_count:
            breakdown.append(
                {
                    "sheet": sheet.title,
                    "finding_count": finding_count,
                    "categories": sorted(categories_seen),
                }
            )

    out = io.BytesIO()
    workbook.save(out)
    return out.getvalue(), breakdown


async def protect_csv(
    data: bytes, protect_text: ProtectText
) -> tuple[bytes, list[dict[str, object]]]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DocumentParseError(str(exc)) from exc

    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    finding_count = 0
    categories_seen: set[str] = set()
    out_rows: list[list[str]] = []
    for row in rows:
        out_row: list[str] = []
        for value in row:
            if not value.strip():
                out_row.append(value)
                continue
            protected, findings = await protect_text(value)
            if findings:
                finding_count += len(findings)
                categories_seen.update(f.category for f in findings)
            out_row.append(protected)
        out_rows.append(out_row)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerows(out_rows)
    breakdown: list[dict[str, object]] = (
        [{"sheet": "csv", "finding_count": finding_count, "categories": sorted(categories_seen)}]
        if finding_count
        else []
    )
    return buf.getvalue().encode("utf-8"), breakdown
