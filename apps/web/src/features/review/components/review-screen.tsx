"use client";

import { CheckIcon, ListChecksIcon, XIcon } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { NoProjectState } from "@/components/no-project-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Surface } from "@/components/surface";
import { TableSkeleton } from "@/components/table-skeleton";
import { errorMessage } from "@/lib/api/errors";
import { categoryLabel, formatConfidence } from "@/lib/format";
import { pendingOnly, sortByCreatedDesc } from "@/lib/review";
import { useProjectStore } from "@/lib/project-store";

import { useApproveReview, useDismissReview, useReviewQueue } from "../api";

export function ReviewScreen() {
  const projectId = useProjectStore((s) => s.selectedProjectId);
  const queue = useReviewQueue(projectId ?? undefined);
  const approve = useApproveReview(projectId ?? undefined);
  const dismiss = useDismissReview(projectId ?? undefined);

  if (!projectId) {
    return (
      <div>
        <PageHeader title="Review Queue" description="Findings below the policy's confidence threshold wait here for a decision." />
        <Surface>
          <NoProjectState />
        </Surface>
      </div>
    );
  }

  const items = sortByCreatedDesc(pendingOnly(queue.data ?? []));

  function doApprove(id: string) {
    approve.mutate(id, {
      onSuccess: () => toast.success("Finding approved and protected."),
      onError: (err) => toast.error(errorMessage(err)),
    });
  }

  function doDismiss(id: string) {
    dismiss.mutate(id, {
      onSuccess: () => toast.success("Finding dismissed."),
      onError: (err) => toast.error(errorMessage(err)),
    });
  }

  return (
    <div>
      <PageHeader
        title="Review Queue"
        description="Low-confidence findings land here instead of being auto-protected or ignored. Approve to protect them, or dismiss to leave them as is."
      />
      <Surface>
        {queue.isError ? (
          <ErrorState error={queue.error} onRetry={() => void queue.refetch()} />
        ) : queue.isLoading ? (
          <TableSkeleton cols={6} />
        ) : items.length === 0 ? (
          <EmptyState
            icon={ListChecksIcon}
            title="Nothing waiting on review"
            description={
              <>
                Findings below the project&apos;s confidence threshold land here. Adjust the threshold under{" "}
                <Link href="/policies" className="font-medium text-primary hover:underline">
                  Policies
                </Link>{" "}
                if you expect more, or fewer, to show up.
              </>
            }
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Category</TableHead>
                <TableHead>Span</TableHead>
                <TableHead>Confidence</TableHead>
                <TableHead>Recognizer</TableHead>
                <TableHead>Already protected</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="font-medium">{categoryLabel(item.category)}</TableCell>
                  <TableCell className="tabular text-muted-foreground">
                    {item.start}-{item.end}
                  </TableCell>
                  <TableCell className="tabular">{formatConfidence(item.confidence)}</TableCell>
                  <TableCell className="text-muted-foreground">{item.recognizer}</TableCell>
                  <TableCell>
                    <Chip tone={item.already_protected ? "savings" : "neutral"}>{item.already_protected ? "Yes" : "No"}</Chip>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1.5">
                      <Button
                        variant="outline"
                        size="xs"
                        onClick={() => doApprove(item.id)}
                        disabled={approve.isPending || dismiss.isPending}
                      >
                        <CheckIcon />
                        Approve
                      </Button>
                      <Button
                        variant="ghost"
                        size="xs"
                        onClick={() => doDismiss(item.id)}
                        disabled={approve.isPending || dismiss.isPending}
                      >
                        <XIcon />
                        Dismiss
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Surface>
    </div>
  );
}
