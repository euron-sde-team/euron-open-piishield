"use client";

import { ArrowDownIcon, BotIcon, ShieldIcon, UndoIcon } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { NoProjectState } from "@/components/no-project-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Textarea } from "@/components/ui/input";
import { Surface, SurfaceHeader } from "@/components/surface";
import { errorMessage } from "@/lib/api/errors";
import { useProjectStore } from "@/lib/project-store";

import { useGatewayProtect, useGatewayRestore } from "../api";

export function AiGatewayScreen() {
  const projectId = useProjectStore((s) => s.selectedProjectId);
  const protect = useGatewayProtect();
  const restore = useGatewayRestore();

  const [prompt, setPrompt] = React.useState("");
  const [scopeId, setScopeId] = React.useState<string | null>(null);
  const [protectedPrompt, setProtectedPrompt] = React.useState<string | null>(null);
  const [modelResponse, setModelResponse] = React.useState("");
  const [restoredResponse, setRestoredResponse] = React.useState<string | null>(null);
  const [placeholdersRestored, setPlaceholdersRestored] = React.useState<number | null>(null);

  if (!projectId) {
    return (
      <div>
        <PageHeader title="AI Gateway" description="Protect a prompt before it reaches any model, then restore placeholders for your own app only." />
        <Surface>
          <NoProjectState />
        </Surface>
      </div>
    );
  }

  function runProtect() {
    if (!prompt.trim() || !projectId) return;
    protect.mutate(
      { project_id: projectId, prompt },
      {
        onSuccess: (result) => {
          setProtectedPrompt(result.protected_prompt);
          setScopeId(result.scope_id);
          setModelResponse(result.protected_prompt);
          setRestoredResponse(null);
          setPlaceholdersRestored(null);
          toast.success(`Protected, ${result.findings.length} finding(s). Send this to the model.`);
        },
        onError: (err) => toast.error(errorMessage(err)),
      },
    );
  }

  function runRestore() {
    if (!scopeId || !modelResponse.trim() || !projectId) return;
    restore.mutate(
      { project_id: projectId, scope_id: scopeId, model_response: modelResponse },
      {
        onSuccess: (result) => {
          setRestoredResponse(result.restored_response);
          setPlaceholdersRestored(result.placeholders_restored);
          toast.success(`Restored ${result.placeholders_restored} placeholder(s).`);
        },
        onError: (err) => toast.error(errorMessage(err)),
      },
    );
  }

  return (
    <div>
      <PageHeader
        title="AI Gateway"
        description="The core flow: protect a prompt before any external model sees it, then restore placeholders only for your own application, never for the model."
      />

      <Surface>
        <SurfaceHeader title="1. Protect the prompt" description="This is what you send to the model instead of the raw prompt." />
        <div className="space-y-3 px-5 pb-5">
          <Textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Summarize this customer's issue: Jane Doe, jane.doe@example.com, called about her card ending in 4242..."
            className="min-h-28 font-mono text-[12.5px]"
          />
          <Button onClick={runProtect} disabled={!prompt.trim() || protect.isPending}>
            <ShieldIcon />
            {protect.isPending ? "Protecting..." : "Protect prompt"}
          </Button>
          {protectedPrompt && scopeId && (
            <div className="space-y-2 rounded-xl bg-muted p-4">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[12px] font-semibold text-muted-foreground uppercase">Protected prompt</span>
                <Chip tone="primary">scope {scopeId.slice(0, 10)}...</Chip>
              </div>
              <pre className="font-mono text-[12.5px] leading-relaxed whitespace-pre-wrap text-foreground">{protectedPrompt}</pre>
            </div>
          )}
        </div>
      </Surface>

      {scopeId && (
        <>
          <div className="my-3 flex items-center justify-center text-muted-foreground">
            <ArrowDownIcon className="size-5" />
          </div>

          <Surface>
            <SurfaceHeader
              title={
                <>
                  <BotIcon className="size-4 text-muted-foreground" />
                  2. Paste the model&apos;s response
                </>
              }
              description="Simulate what an external model would send back, referencing the placeholders above. Edit this freely."
            />
            <div className="space-y-3 px-5 pb-5">
              <Textarea
                value={modelResponse}
                onChange={(e) => setModelResponse(e.target.value)}
                className="min-h-28 font-mono text-[12.5px]"
              />
              <Button onClick={runRestore} disabled={!modelResponse.trim() || restore.isPending}>
                <UndoIcon />
                {restore.isPending ? "Restoring..." : "Restore for my app"}
              </Button>
              {restoredResponse !== null && (
                <div className="space-y-2 rounded-xl bg-muted p-4">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[12px] font-semibold text-muted-foreground uppercase">Restored response</span>
                    <Chip tone="savings">{placeholdersRestored} placeholder(s) restored</Chip>
                  </div>
                  <pre className="font-mono text-[12.5px] leading-relaxed whitespace-pre-wrap text-foreground">{restoredResponse}</pre>
                  <p className="text-[12px] text-muted-foreground">
                    This restored text is for your application only. The model itself only ever saw the protected prompt above.
                  </p>
                </div>
              )}
            </div>
          </Surface>
        </>
      )}
    </div>
  );
}
