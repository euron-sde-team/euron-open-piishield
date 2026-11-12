"use client";

import { CheckCircle2Icon, ScanLineIcon, ShieldIcon } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { CopyButton } from "@/components/copy-button";
import { NoProjectState } from "@/components/no-project-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { SimpleSelect } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/input";
import { Surface, SurfaceHeader } from "@/components/surface";
import { usePolicy } from "@/features/policies/api";
import { errorMessage } from "@/lib/api/errors";
import type { Finding, MaskingMethod, ProtectedFinding } from "@/lib/api/types";
import { categoryLabel, formatConfidence, methodLabel } from "@/lib/format";
import { MASKING_METHODS } from "@/lib/policy";
import { useProjectStore } from "@/lib/project-store";

import { useProtectJson, useProtectText, useScanText } from "../api";
import { FindingHighlighter } from "./finding-highlighter";

type Mode = "text" | "json";

export function ScanScreen() {
  const projectId = useProjectStore((s) => s.selectedProjectId);
  const policy = usePolicy(projectId ?? undefined);
  const scanText = useScanText();
  const protectText = useProtectText();
  const protectJson = useProtectJson();

  const [mode, setMode] = React.useState<Mode>("text");
  const [input, setInput] = React.useState("");
  const [findings, setFindings] = React.useState<Finding[]>([]);
  const [protectedFindings, setProtectedFindings] = React.useState<ProtectedFinding[] | null>(null);
  const [protectedText, setProtectedText] = React.useState<string | null>(null);
  const [protectedJson, setProtectedJson] = React.useState<unknown>(null);
  const [overrides, setOverrides] = React.useState<Record<string, string>>({});
  const [jsonError, setJsonError] = React.useState<string | null>(null);

  // Seed per-category overrides from the policy's configured methods once it loads,
  // for every category currently found, so the selects are never blank when a method
  // is already known.
  React.useEffect(() => {
    if (!policy.data) return;
    setOverrides((prev) => ({ ...policy.data!.masking_method, ...prev }));
  }, [policy.data]);

  const categories = React.useMemo(() => {
    const set = new Set<string>();
    findings.forEach((f) => set.add(f.category));
    return Array.from(set);
  }, [findings]);

  function reset() {
    setFindings([]);
    setProtectedFindings(null);
    setProtectedText(null);
    setProtectedJson(null);
    setJsonError(null);
  }

  function runScan() {
    if (!projectId) return;
    reset();
    if (mode === "json") {
      setJsonError(null);
      try {
        JSON.parse(input);
      } catch {
        setJsonError("Not valid JSON. Fix the input, or switch to text mode.");
        return;
      }
    }
    scanText.mutate(
      { project_id: projectId, text: mode === "json" ? input : input },
      {
        onSuccess: (result) => setFindings(result.findings),
        onError: (err) => toast.error(errorMessage(err)),
      },
    );
  }

  function runProtect() {
    if (!projectId) return;
    // Only MASKING_METHODS values are ever written into `overrides`, via the SimpleSelect
    // options rendered below, so this cast is safe.
    const method_overrides = Object.fromEntries(Object.entries(overrides).filter(([, v]) => !!v)) as Record<string, MaskingMethod>;
    if (mode === "json") {
      let payload: unknown;
      try {
        payload = JSON.parse(input);
      } catch {
        setJsonError("Not valid JSON. Fix the input, or switch to text mode.");
        return;
      }
      protectJson.mutate(
        { project_id: projectId, payload, method_overrides },
        {
          onSuccess: (result) => {
            setProtectedJson(result.protected);
            setProtectedFindings(result.findings);
            toast.success(`Protected ${result.findings.length} finding(s).`);
          },
          onError: (err) => toast.error(errorMessage(err)),
        },
      );
    } else {
      protectText.mutate(
        { project_id: projectId, text: input, method_overrides },
        {
          onSuccess: (result) => {
            setProtectedText(result.protected);
            setProtectedFindings(result.findings);
            toast.success(`Protected ${result.findings.length} finding(s).`);
          },
          onError: (err) => toast.error(errorMessage(err)),
        },
      );
    }
  }

  if (!projectId) {
    return (
      <div>
        <PageHeader title="Scan Center" description="Scan text or JSON for PII, then protect it with a method per category." />
        <Surface>
          <NoProjectState />
        </Surface>
      </div>
    );
  }

  const busy = scanText.isPending || protectText.isPending || protectJson.isPending;

  return (
    <div>
      <PageHeader
        title="Scan Center"
        description="Scan only to see what would be found, or protect to mask, redact or tokenize it right away."
      />

      <Surface>
        <SurfaceHeader
          title="Input"
          action={
            <Tabs value={mode} onValueChange={(v) => setMode(v as Mode)}>
              <TabsList>
                <TabsTrigger value="text">Text</TabsTrigger>
                <TabsTrigger value="json">JSON</TabsTrigger>
              </TabsList>
            </Tabs>
          }
        />
        <div className="space-y-3 px-5 pb-5">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              mode === "json"
                ? '{"customer": {"email": "jane@example.com", "pan": "ABCPE1234F"}}'
                : "Paste text with emails, phone numbers, PANs, card numbers..."
            }
            className="min-h-40 font-mono text-[12.5px]"
          />
          {jsonError && <p className="text-xs font-medium text-danger">{jsonError}</p>}
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" onClick={runScan} disabled={!input.trim() || busy}>
              <ScanLineIcon />
              {scanText.isPending ? "Scanning..." : "Scan only"}
            </Button>
            <Button onClick={runProtect} disabled={!input.trim() || busy}>
              <ShieldIcon />
              {protectText.isPending || protectJson.isPending ? "Protecting..." : "Protect"}
            </Button>
          </div>
        </div>
      </Surface>

      {findings.length > 0 && !protectedFindings && (
        <Surface className="mt-4">
          <SurfaceHeader title="Findings" description={`${findings.length} finding(s), not yet protected.`} />
          <div className="px-5 pb-4">
            {mode === "text" && <FindingHighlighter text={input} findings={findings} />}
          </div>
          <FindingsTable findings={findings} />
        </Surface>
      )}

      {findings.length > 0 && !protectedFindings && (
        <Surface className="mt-4">
          <SurfaceHeader title="Protection method per category" description="Defaults come from this project's policy; override as needed." />
          <div className="grid gap-3 px-5 pb-5 sm:grid-cols-2">
            {categories.map((c) => (
              <div key={c} className="flex items-center justify-between gap-3">
                <span className="text-[13px] text-foreground">{categoryLabel(c)}</span>
                <SimpleSelect
                  value={overrides[c] ?? ""}
                  onValueChange={(v) => setOverrides((prev) => ({ ...prev, [c]: v }))}
                  options={MASKING_METHODS.map((m) => ({ value: m, label: methodLabel(m) }))}
                  placeholder="Choose method"
                  size="sm"
                  className="w-44"
                />
              </div>
            ))}
          </div>
        </Surface>
      )}

      {protectedFindings && (
        <>
          <Surface className="mt-4">
            <SurfaceHeader
              title="Protected output"
              titleExtra={
                <Chip tone="savings" dot>
                  <CheckCircle2Icon className="size-3" />
                  {protectedFindings.length} protected
                </Chip>
              }
              action={<CopyButton value={mode === "json" ? JSON.stringify(protectedJson, null, 2) : protectedText ?? ""} label="Copy" />}
            />
            <div className="px-5 pb-5">
              <pre className="max-h-96 overflow-auto rounded-xl bg-muted p-4 font-mono text-[12.5px] leading-relaxed whitespace-pre-wrap">
                {mode === "json" ? JSON.stringify(protectedJson, null, 2) : protectedText}
              </pre>
            </div>
          </Surface>
          <Surface className="mt-4">
            <SurfaceHeader title="Findings and methods applied" />
            <ProtectedFindingsTable findings={protectedFindings} />
          </Surface>
        </>
      )}
    </div>
  );
}

function FindingsTable({ findings }: { findings: Finding[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Category</TableHead>
          <TableHead>Span</TableHead>
          <TableHead>Confidence</TableHead>
          <TableHead>Recognizer</TableHead>
          <TableHead>Checksum</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {findings.map((f, i) => (
          <TableRow key={i}>
            <TableCell className="font-medium">{categoryLabel(f.category)}</TableCell>
            <TableCell className="tabular text-muted-foreground">
              {f.start}-{f.end}
            </TableCell>
            <TableCell className="tabular">{formatConfidence(f.confidence)}</TableCell>
            <TableCell className="text-muted-foreground">{f.recognizer}</TableCell>
            <TableCell>
              {f.checksum_valid === null || f.checksum_valid === undefined ? (
                <span className="text-faint">n/a</span>
              ) : (
                <Chip tone={f.checksum_valid ? "savings" : "danger"}>{f.checksum_valid ? "Valid" : "Invalid"}</Chip>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function ProtectedFindingsTable({ findings }: { findings: ProtectedFinding[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Category</TableHead>
          <TableHead>Method</TableHead>
          <TableHead>Confidence</TableHead>
          <TableHead>Placeholder</TableHead>
          <TableHead>In review</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {findings.map((f, i) => (
          <TableRow key={i}>
            <TableCell className="font-medium">{categoryLabel(f.category)}</TableCell>
            <TableCell>
              <Chip tone="primary">{methodLabel(f.method)}</Chip>
            </TableCell>
            <TableCell className="tabular">{formatConfidence(f.confidence)}</TableCell>
            <TableCell className="font-mono text-[12px] text-muted-foreground">{f.placeholder ?? "-"}</TableCell>
            <TableCell>{f.in_review ? <Chip tone="warning">Yes</Chip> : <Chip tone="neutral">No</Chip>}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
