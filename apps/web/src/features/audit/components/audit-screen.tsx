"use client";

import { ChevronDownIcon, ScrollTextIcon } from "lucide-react";
import * as React from "react";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Surface } from "@/components/surface";
import { TableSkeleton } from "@/components/table-skeleton";
import { auditDetailSummary, hasSummarizableDetails } from "@/lib/audit";
import type { AuditEntry } from "@/lib/api/types";
import { categoryLabel, formatDateTime } from "@/lib/format";

import { useAuditLog } from "../api";

function DetailsCell({ entry }: { entry: AuditEntry }) {
  const [open, setOpen] = React.useState(false);
  const summary = auditDetailSummary(entry);
  if (!hasSummarizableDetails(entry)) {
    return <span className="text-faint">-</span>;
  }
  return (
    <div>
      <button type="button" onClick={() => setOpen((o) => !o)} className="flex items-center gap-1 text-[12px] text-muted-foreground hover:text-foreground">
        <ChevronDownIcon className={`size-3 transition-transform ${open ? "rotate-180" : ""}`} />
        {summary.length} field(s)
      </button>
      {open && (
        <div className="mt-1 space-y-0.5 font-mono text-[11.5px] text-muted-foreground">
          {summary.map((s) => (
            <div key={s.key}>
              {s.key}: {s.value}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function AuditScreen() {
  const [limit, setLimit] = React.useState(50);
  const [action, setAction] = React.useState("");
  const [appliedAction, setAppliedAction] = React.useState<string | undefined>(undefined);
  const audit = useAuditLog(limit, appliedAction);

  return (
    <div>
      <PageHeader
        title="Audit Log"
        description="Every scan, protect, review decision and vault action, across this org. This log never contains an original value, only what happened and to what category."
      />

      <Surface>
        <div className="flex flex-wrap items-end gap-3 px-5 pt-4 pb-3">
          <div className="min-w-48 flex-1">
            <Input
              value={action}
              onChange={(e) => setAction(e.target.value)}
              placeholder="Filter by action, e.g. scan, protect.text"
              className="h-8 text-[13px]"
            />
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setLimit(50);
              setAppliedAction(action.trim() || undefined);
            }}
          >
            Apply filter
          </Button>
        </div>

        {audit.isError ? (
          <ErrorState error={audit.error} onRetry={() => void audit.refetch()} />
        ) : audit.isLoading ? (
          <TableSkeleton cols={5} />
        ) : !audit.data || audit.data.items.length === 0 ? (
          <EmptyState
            icon={ScrollTextIcon}
            title="No audit entries yet"
            description="Scan, protect, review and vault actions will appear here as they happen."
          />
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>When</TableHead>
                  <TableHead>Actor</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Categories</TableHead>
                  <TableHead>Findings</TableHead>
                  <TableHead>Details</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {audit.data.items.map((entry) => (
                  <TableRow key={entry.id}>
                    <TableCell className="text-muted-foreground">{formatDateTime(entry.created_at)}</TableCell>
                    <TableCell>
                      <div className="font-medium">{entry.actor_label}</div>
                      <div className="text-[11.5px] text-muted-foreground">{entry.actor_kind}</div>
                    </TableCell>
                    <TableCell className="font-mono text-[12.5px]">{entry.action}</TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {entry.categories.length === 0 ? (
                          <span className="text-faint">-</span>
                        ) : (
                          entry.categories.map((c) => <Chip key={c}>{categoryLabel(c)}</Chip>)
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="tabular">{entry.finding_count}</TableCell>
                    <TableCell>
                      <DetailsCell entry={entry} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {audit.data.next_cursor && (
              <div className="flex justify-center py-4">
                <Button variant="outline" onClick={() => setLimit((l) => l + 50)}>
                  Load more
                </Button>
              </div>
            )}
          </>
        )}
      </Surface>
    </div>
  );
}
