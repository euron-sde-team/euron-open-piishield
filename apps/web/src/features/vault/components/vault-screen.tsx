"use client";

import { EyeIcon, LockIcon, PlusIcon, Trash2Icon } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/empty-state";
import { NoProjectState } from "@/components/no-project-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field, FieldError } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Surface, SurfaceHeader } from "@/components/surface";
import { ApiError, errorMessage } from "@/lib/api/errors";
import { categoryLabel } from "@/lib/format";
import { useAuthStore } from "@/lib/auth-store";
import { useProjectStore } from "@/lib/project-store";

import { useCreateVaultGrant, useDetokenize, useRevokeVaultGrant, useVaultGrants } from "../api";

function DetokenizeForm({ projectId }: { projectId: string }) {
  const detokenize = useDetokenize();
  const [placeholder, setPlaceholder] = React.useState("");
  const [scopeId, setScopeId] = React.useState("");
  const [revealed, setRevealed] = React.useState(false);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setRevealed(false);
    detokenize.mutate(
      { project_id: projectId, placeholder, scope_id: scopeId },
      {
        onError: (err) => {
          if (err instanceof ApiError && err.isForbidden) return; // rendered inline below
          toast.error(errorMessage(err));
        },
      },
    );
  }

  const forbidden = detokenize.isError && detokenize.error instanceof ApiError && detokenize.error.isForbidden;

  return (
    <Surface>
      <SurfaceHeader title="Detokenize a value" description="Resolves a placeholder back to its original value, within the scope it was protected under." />
      <form onSubmit={submit} className="space-y-4 px-5 pb-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Placeholder" htmlFor="vault-placeholder">
            <Input id="vault-placeholder" value={placeholder} onChange={(e) => setPlaceholder(e.target.value)} placeholder="[EMAIL_1]" className="font-mono text-[12.5px]" />
          </Field>
          <Field label="Scope ID" htmlFor="vault-scope">
            <Input id="vault-scope" value={scopeId} onChange={(e) => setScopeId(e.target.value)} placeholder="from a protect call" className="font-mono text-[12.5px]" />
          </Field>
        </div>
        <Button type="submit" disabled={!placeholder.trim() || !scopeId.trim() || detokenize.isPending}>
          {detokenize.isPending ? "Looking up..." : "Detokenize"}
        </Button>
        {forbidden && <FieldError>You do not have vault access for this project.</FieldError>}
        {detokenize.data && (
          <div className="rounded-xl bg-muted p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-[12px] font-semibold text-muted-foreground uppercase">{categoryLabel(detokenize.data.category)}</div>
                <div className="mt-1 font-mono text-[13px]">
                  {revealed ? detokenize.data.value : "••••••••••••"}
                </div>
              </div>
              <Button variant="outline" size="sm" onClick={() => setRevealed((r) => !r)}>
                <EyeIcon />
                {revealed ? "Hide" : "Reveal"}
              </Button>
            </div>
            <p className="mt-2 text-[11.5px] text-muted-foreground">Sensitive value. Shown only after you click Reveal.</p>
          </div>
        )}
      </form>
    </Surface>
  );
}

function GrantsPanel() {
  const grants = useVaultGrants(true);
  const create = useCreateVaultGrant();
  const revoke = useRevokeVaultGrant();
  const [userId, setUserId] = React.useState("");
  const [apiKeyId, setApiKeyId] = React.useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!userId.trim() && !apiKeyId.trim()) {
      toast.error("Provide a user ID or an API key ID.");
      return;
    }
    create.mutate(
      { user_id: userId.trim() || null, api_key_id: apiKeyId.trim() || null },
      {
        onSuccess: () => {
          toast.success("Grant created.");
          setUserId("");
          setApiKeyId("");
        },
        onError: (err) => toast.error(errorMessage(err)),
      },
    );
  }

  const active = (grants.data ?? []).filter((g) => !g.revoked_at);
  const forbidden = grants.isError && grants.error instanceof ApiError && grants.error.isForbidden;

  return (
    <Surface className="mt-4">
      <SurfaceHeader title="Vault grants" description="Who currently holds vault access, in this org." />
      <div className="px-5 pb-5">
        {forbidden ? (
          <div className="py-4 text-[13px] text-muted-foreground">
            You do not have permission to view vault grants for this project.
          </div>
        ) : grants.isLoading ? (
          <div className="py-4 text-[13px] text-muted-foreground">Loading...</div>
        ) : active.length === 0 ? (
          <div className="py-4 text-[13px] text-muted-foreground">No one holds vault access yet.</div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Grantee</TableHead>
                <TableHead>Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {active.map((g) => (
                <TableRow key={g.id}>
                  <TableCell className="font-mono text-[12.5px]">
                    {g.user_id ? `User ${g.user_id.slice(0, 8)}...` : g.api_key_id ? `API key ${g.api_key_id.slice(0, 8)}...` : "Unknown"}
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="xs"
                      onClick={() =>
                        revoke.mutate(g.id, {
                          onSuccess: () => toast.success("Grant revoked."),
                          onError: (err) => toast.error(errorMessage(err)),
                        })
                      }
                      disabled={revoke.isPending}
                    >
                      <Trash2Icon />
                      Revoke
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

        {!forbidden && (
        <form onSubmit={submit} className="mt-4 flex flex-wrap items-end gap-3 border-t border-hairline pt-4">
          <Field label="User ID" htmlFor="grant-user" className="min-w-40 flex-1">
            <Input id="grant-user" value={userId} onChange={(e) => setUserId(e.target.value)} placeholder="uuid" className="font-mono text-[12.5px]" />
          </Field>
          <Field label="or API key ID" htmlFor="grant-key" className="min-w-40 flex-1">
            <Input id="grant-key" value={apiKeyId} onChange={(e) => setApiKeyId(e.target.value)} placeholder="uuid" className="font-mono text-[12.5px]" />
          </Field>
          <Button type="submit" disabled={create.isPending}>
            <PlusIcon />
            Grant access
          </Button>
        </form>
        )}
      </div>
    </Surface>
  );
}

export function VaultScreen() {
  const projectId = useProjectStore((s) => s.selectedProjectId);
  const user = useAuthStore((s) => s.user);

  if (!projectId) {
    return (
      <div>
        <PageHeader title="Token Vault" description="Reverse a tokenized value back to the original, for someone explicitly granted access." />
        <Surface>
          <NoProjectState />
        </Surface>
      </div>
    );
  }

  if (!user?.vault_access) {
    return (
      <div>
        <PageHeader title="Token Vault" description="Reverse a tokenized value back to the original, for someone explicitly granted access." />
        <Surface>
          <EmptyState
            icon={LockIcon}
            title="You do not have vault access"
            description="Detokenizing a value requires a separate grant, even for an owner. This is by design: tokenizing and reading back the original are kept apart so a compromised account cannot silently unmask everything it tokenized. Ask whoever manages vault grants in your org to add you."
          />
        </Surface>
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="Token Vault" description="Reverse a tokenized value back to the original, for someone explicitly granted access." />
      <DetokenizeForm projectId={projectId} />
      <GrantsPanel />
    </div>
  );
}
