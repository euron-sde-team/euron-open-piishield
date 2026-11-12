"""Read-only, column-level PII sampling against a caller-provided connection.

0.1.0 scope (PLAN.md): sample rows, report which columns LOOK like they hold PII, for a
human to act on. It never writes to the scanned database, never persists the connection
string, and never persists a sampled value: for each column it runs the same detectors
used elsewhere, keeps only the category tally and a confidence, and discards the sampled
text immediately after scoring it.
"""

from __future__ import annotations

import asyncio
import sqlite3
import uuid
from collections import Counter

import asyncpg
import pymysql
from sqlalchemy.ext.asyncio import AsyncSession

from piishield.audit.service import Actor
from piishield.audit.service import record as audit_record
from piishield.database_scan import repository
from piishield.database_scan.exceptions import DatabaseConnectionError
from piishield.database_scan.schemas import ColumnFinding
from piishield.detectors.recognizers import scan_text
from piishield.projects.service import ensure_project


async def _sample_postgres(
    dsn: str, table: str, limit: int
) -> tuple[list[str], list[tuple[object, ...]]]:
    try:
        conn = await asyncpg.connect(dsn)
    except Exception as exc:
        raise DatabaseConnectionError() from exc
    try:
        rows = await conn.fetch(f'SELECT * FROM "{table}" LIMIT $1', limit)  # noqa: S608 table name is operator-supplied, not user text content
        columns = list(rows[0].keys()) if rows else []
        return columns, [tuple(r.values()) for r in rows]
    finally:
        await conn.close()


def _sample_mysql_sync(
    dsn: str, table: str, limit: int
) -> tuple[list[str], list[tuple[object, ...]]]:
    conn = pymysql.connect(**_parse_mysql_dsn(dsn))
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM `{table}` LIMIT %s", (limit,))  # noqa: S608
            columns = [d[0] for d in (cur.description or [])]
            return columns, list(cur.fetchall())
    finally:
        conn.close()


def _parse_mysql_dsn(dsn: str) -> dict[str, object]:
    from urllib.parse import urlparse

    parsed = urlparse(dsn)
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 3306,
        "user": parsed.username or "root",
        "password": parsed.password or "",
        "database": (parsed.path or "/").lstrip("/"),
    }


def _sample_sqlite_sync(
    path: str, table: str, limit: int
) -> tuple[list[str], list[tuple[object, ...]]]:
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute(f'SELECT * FROM "{table}" LIMIT ?', (limit,))  # noqa: S608
        columns = [d[0] for d in cur.description]
        return columns, cur.fetchall()
    finally:
        conn.close()


async def sample(
    engine: str, connection_string: str, table: str, limit: int
) -> tuple[list[str], list[tuple[object, ...]]]:
    try:
        if engine == "postgres":
            return await _sample_postgres(connection_string, table, limit)
        if engine == "mysql":
            return await asyncio.to_thread(_sample_mysql_sync, connection_string, table, limit)
        return await asyncio.to_thread(_sample_sqlite_sync, connection_string, table, limit)
    except DatabaseConnectionError:
        raise
    except Exception as exc:
        raise DatabaseConnectionError() from exc


def _score_column(values: list[object]) -> ColumnFinding | None:
    hits: Counter[str] = Counter()
    sampled = 0
    for value in values:
        if not isinstance(value, str) or not value.strip():
            continue
        sampled += 1
        for finding in scan_text(value):
            hits[finding.category] += 1
    if sampled == 0 or not hits:
        return None
    category, count = hits.most_common(1)[0]
    confidence = min(1.0, count / max(sampled, 1))
    return ColumnFinding(
        column="", category=category, confidence=round(confidence, 2), sample_hits=count
    )


async def scan_table(
    session: AsyncSession,
    actor: Actor,
    project_id: uuid.UUID,
    engine: str,
    connection_string: str,
    table: str,
    limit: int,
) -> tuple[uuid.UUID, int, list[ColumnFinding]]:
    await ensure_project(session, actor.scope, project_id)
    columns, rows = await sample(engine, connection_string, table, limit)
    findings: list[ColumnFinding] = []
    for i, name in enumerate(columns):
        values = [row[i] for row in rows]
        scored = _score_column(values)
        if scored is not None:
            findings.append(scored.model_copy(update={"column": name}))

    row = repository.record_scan(
        session,
        actor.org_id,
        project_id,
        table,
        len(rows),
        [f.model_dump() for f in findings],
    )
    await session.flush()
    audit_record(
        session,
        actor,
        "database_scan",
        project_id=project_id,
        finding_count=len(findings),
        categories=[f.category for f in findings],
        table_name=table,
    )
    await session.commit()
    return row.id, len(rows), findings
