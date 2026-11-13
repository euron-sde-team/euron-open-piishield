"use client";

import { FileSearchIcon, ListChecksIcon, LockIcon, ScanLineIcon } from "lucide-react";

import { ErrorState } from "@/components/error-state";
import { KpiTile } from "@/components/kpi-tile";
import { PageHeader } from "@/components/page-header";
import { Surface, SurfaceHeader } from "@/components/surface";
import { categoryLabel } from "@/lib/format";

import { useSummaryReport } from "../api";

function BreakdownBar({ label, count, max }: { label: string; count: number; max: number }) {
  const pct = max > 0 ? Math.max(4, Math.round((count / max) * 100)) : 0;
  return (
    <div className="flex items-center gap-3">
      <div className="w-32 shrink-0 truncate text-[13px] text-foreground">{categoryLabel(label)}</div>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
      </div>
      <div className="w-10 shrink-0 text-right text-[12.5px] tabular text-muted-foreground">{count}</div>
    </div>
  );
}

export function OverviewScreen() {
  const summary = useSummaryReport();

  return (
    <div>
      <PageHeader
        title="Overview"
        description="Org-wide totals across every project: scans run, findings detected, items waiting on review, and values held in the vault."
      />

      {summary.isError ? (
        <Surface>
          <ErrorState error={summary.error} onRetry={() => void summary.refetch()} />
        </Surface>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <KpiTile label="Total scans" value={summary.data?.total_scans ?? 0} icon={ScanLineIcon} loading={summary.isLoading} />
            <KpiTile label="Total findings" value={summary.data?.total_findings ?? 0} icon={FileSearchIcon} accent="warning" loading={summary.isLoading} />
            <KpiTile label="Pending review" value={summary.data?.pending_review ?? 0} icon={ListChecksIcon} accent="danger" loading={summary.isLoading} />
            <KpiTile label="Vault entries" value={summary.data?.vault_entries ?? 0} icon={LockIcon} accent="savings" loading={summary.isLoading} />
          </div>

          <Surface className="mt-4">
            <SurfaceHeader title="Findings by category" description="Where detections land, across every project in your org." />
            <div className="space-y-3 px-5 pb-5">
              {summary.isLoading ? (
                <div className="py-6 text-center text-[13px] text-muted-foreground">Loading...</div>
              ) : summary.data && summary.data.findings_by_category.length > 0 ? (
                summary.data.findings_by_category
                  .slice()
                  .sort((a, b) => b.count - a.count)
                  .map((row) => (
                    <BreakdownBar
                      key={row.category}
                      label={row.category}
                      count={row.count}
                      max={summary.data?.findings_by_category[0]?.count ?? 1}
                    />
                  ))
              ) : (
                <div className="py-6 text-center text-[13px] text-muted-foreground">
                  No findings yet. Run a scan from Scan Center to see categories appear here.
                </div>
              )}
            </div>
          </Surface>
        </>
      )}
    </div>
  );
}
