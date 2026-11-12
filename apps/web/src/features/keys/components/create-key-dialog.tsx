"use client";

import { CheckCircle2Icon, TriangleAlertIcon } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { CopyButton } from "@/components/copy-button";
import { Button } from "@/components/ui/button";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/ui/label";
import { SimpleSelect } from "@/components/ui/select";
import { errorMessage } from "@/lib/api/errors";
import type { ApiKeyCreated, ApiKeyScope } from "@/lib/api/types";

import { useCreateApiKey } from "../api";

function KeyRevealed({ created }: { created: ApiKeyCreated }) {
  return (
    <div className="space-y-4">
      <div className="flex gap-3 rounded-xl bg-warning-soft px-4 py-3 text-[13px]">
        <TriangleAlertIcon className="mt-0.5 size-4 shrink-0 text-warning" />
        <p className="text-foreground">
          Copy this key now. It is shown <strong>once</strong>; PIIShield cannot show it again.
        </p>
      </div>
      <div className="flex items-center gap-2 rounded-xl bg-muted p-1.5 pl-3.5">
        <code className="min-w-0 flex-1 truncate font-mono text-[12.5px] select-all" data-testid="new-key">
          {created.key}
        </code>
        <CopyButton value={created.key} label="Copy key" variant="default" />
      </div>
    </div>
  );
}

export function CreateKeyDialog({
  open,
  onOpenChange,
  projectId,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  projectId: string;
}) {
  const create = useCreateApiKey(projectId);
  const [name, setName] = React.useState("");
  const [scope, setScope] = React.useState<ApiKeyScope>("read");
  const [error, setError] = React.useState<string | null>(null);
  const [created, setCreated] = React.useState<ApiKeyCreated | null>(null);

  React.useEffect(() => {
    if (open) {
      setName("");
      setScope("read");
      setError(null);
      setCreated(null);
    }
  }, [open]);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setError('Name it after where it runs, for example "production".');
      return;
    }
    setError(null);
    create.mutate(
      { name: name.trim(), scope },
      {
        onSuccess: (key) => {
          setCreated(key);
          toast.success("API key created.");
        },
        onError: (err) => setError(errorMessage(err)),
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !create.isPending && onOpenChange(o)}>
      <DialogContent className={created ? "max-w-2xl" : "max-w-lg"}>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {created && <CheckCircle2Icon className="size-5 text-savings" />}
            {created ? `Key "${created.name}" is ready` : "New API key"}
          </DialogTitle>
          <DialogDescription>
            {created
              ? "Use it instead of signing in to call the API for this project."
              : "Applications use this key instead of a user session. Read keys can scan and protect; write keys can also manage policy and recognizers."}
          </DialogDescription>
        </DialogHeader>
        {created ? (
          <>
            <DialogBody>
              <KeyRevealed created={created} />
            </DialogBody>
            <DialogFooter>
              <Button onClick={() => onOpenChange(false)}>I have copied the key</Button>
            </DialogFooter>
          </>
        ) : (
          <form onSubmit={submit} className="flex min-h-0 flex-col" noValidate>
            <DialogBody className="space-y-4">
              <Field label="Name" htmlFor="key-name" error={error ?? undefined}>
                <Input id="key-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="production" />
              </Field>
              <Field label="Scope" htmlFor="key-scope" hint="Read can scan and protect. Write can also change policy and recognizers.">
                <SimpleSelect
                  id="key-scope"
                  value={scope}
                  onValueChange={(v) => setScope(v as ApiKeyScope)}
                  options={[
                    { value: "read", label: "Read" },
                    { value: "write", label: "Write" },
                  ]}
                />
              </Field>
            </DialogBody>
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={create.isPending}>
                {create.isPending ? "Creating..." : "Create key"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
