"use client";

import { KeyRoundIcon, PlusIcon, Trash2Icon } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/confirm-dialog";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { NoProjectState } from "@/components/no-project-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ScopeChip } from "@/components/status-chip";
import { Surface } from "@/components/surface";
import { TableSkeleton } from "@/components/table-skeleton";
import { errorMessage } from "@/lib/api/errors";
import { formatDateTime } from "@/lib/format";
import { useProjectStore } from "@/lib/project-store";

import { useApiKeys, useRevokeApiKey } from "../api";
import { CreateKeyDialog } from "./create-key-dialog";

export function KeysScreen() {
  const projectId = useProjectStore((s) => s.selectedProjectId);
  const keys = useApiKeys(projectId ?? undefined);
  const revoke = useRevokeApiKey(projectId ?? undefined);
  const [createOpen, setCreateOpen] = React.useState(false);
  const [revokeTarget, setRevokeTarget] = React.useState<{ id: string; name: string } | null>(null);

  if (!projectId) {
    return (
      <div>
        <PageHeader title="API Keys" description="Keys applications use to call the PIIShield API for this project." />
        <Surface>
          <NoProjectState />
        </Surface>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="API Keys"
        description="Keys applications use to call the PIIShield API for this project, instead of signing in."
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <PlusIcon />
            New key
          </Button>
        }
      />

      <Surface>
        {keys.isError ? (
          <ErrorState error={keys.error} onRetry={() => void keys.refetch()} />
        ) : keys.isLoading ? (
          <TableSkeleton cols={5} />
        ) : !keys.data || keys.data.length === 0 ? (
          <EmptyState
            icon={KeyRoundIcon}
            title="No API keys yet"
            description="Create a key so an application can scan and protect data for this project without a user session."
            action={<Button onClick={() => setCreateOpen(true)}>New key</Button>}
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Prefix</TableHead>
                <TableHead>Scope</TableHead>
                <TableHead>Last used</TableHead>
                <TableHead>Status</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {keys.data.map((k) => (
                <TableRow key={k.id}>
                  <TableCell className="font-medium">{k.name}</TableCell>
                  <TableCell className="font-mono text-[12px] text-muted-foreground">{k.prefix}...</TableCell>
                  <TableCell>
                    <ScopeChip scope={k.scope} />
                  </TableCell>
                  <TableCell className="text-muted-foreground">{k.last_used_at ? formatDateTime(k.last_used_at) : "Never"}</TableCell>
                  <TableCell className="text-muted-foreground">{k.revoked_at ? "Revoked" : "Active"}</TableCell>
                  <TableCell>
                    {!k.revoked_at && (
                      <Button variant="ghost" size="icon-xs" aria-label={`Revoke ${k.name}`} onClick={() => setRevokeTarget({ id: k.id, name: k.name })}>
                        <Trash2Icon />
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Surface>

      <CreateKeyDialog open={createOpen} onOpenChange={setCreateOpen} projectId={projectId} />

      <ConfirmDialog
        open={!!revokeTarget}
        onOpenChange={(o) => !o && setRevokeTarget(null)}
        title={`Revoke "${revokeTarget?.name}"?`}
        description="Any application using this key will immediately lose access. This cannot be undone."
        confirmLabel="Revoke key"
        pending={revoke.isPending}
        onConfirm={() => {
          if (!revokeTarget) return;
          revoke.mutate(revokeTarget.id, {
            onSuccess: () => {
              toast.success("Key revoked.");
              setRevokeTarget(null);
            },
            onError: (err) => toast.error(errorMessage(err)),
          });
        }}
      />
    </div>
  );
}
