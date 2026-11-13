"""Dashboard summary report, with the response cache documented in PLAN.md's caching
table: Postgres rollup query, 15 second Redis (or in-process memory) response cache keyed
by org id, so a dashboard left open does not re-run four aggregate queries on every poll.
"""

from __future__ import annotations

import orjson
from sqlalchemy.ext.asyncio import AsyncSession

from piishield.core.db import OrgScope
from piishield.core.kv import KV
from piishield.reports import repository
from piishield.reports.schemas import CategoryCount, SummaryReport

_TTL_S = 15


def _cache_key(scope: OrgScope) -> str:
    return f"piishield:report_summary:{scope.org_id}"


async def summary(session: AsyncSession, kv: KV, scope: OrgScope) -> SummaryReport:
    cached = await kv.get(_cache_key(scope))
    if cached is not None:
        return SummaryReport.model_validate(orjson.loads(cached))

    total_scans, total_findings = await repository.totals(session, scope)
    pending_review = await repository.pending_review_count(session, scope)
    by_category = await repository.findings_by_category(session, scope)
    vault_entries = await repository.vault_entry_count(session, scope)

    report = SummaryReport(
        total_scans=total_scans,
        total_findings=total_findings,
        pending_review=pending_review,
        findings_by_category=[CategoryCount(category=c, count=n) for c, n in by_category],
        vault_entries=vault_entries,
    )
    await kv.set(_cache_key(scope), orjson.dumps(report.model_dump()), _TTL_S)
    return report
