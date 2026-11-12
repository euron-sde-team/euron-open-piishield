import type { AuditEntry } from "./api/types";

/**
 * Picks a handful of non-sensitive, interesting fields out of an audit entry's open
 * `details` object for an inline summary row, instead of rendering it raw. The log
 * never contains an original value (AC11), so this is safe to show without a vault
 * check; anything not recognized stays in the raw/collapsed panel.
 */
const SUMMARY_KEYS = ["source", "scope_id", "method", "engine", "table_name", "rows_sampled"] as const;

export function auditDetailSummary(entry: AuditEntry): Array<{ key: string; value: string }> {
  const details = entry.details ?? {};
  const out: Array<{ key: string; value: string }> = [];
  for (const key of SUMMARY_KEYS) {
    const value = (details as Record<string, unknown>)[key];
    if (value === undefined || value === null) continue;
    out.push({ key, value: String(value) });
  }
  return out;
}

export function hasSummarizableDetails(entry: AuditEntry): boolean {
  return auditDetailSummary(entry).length > 0;
}
