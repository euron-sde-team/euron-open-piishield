"use client";

import { CheckCircle2Icon, DownloadIcon, UploadCloudIcon } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { NoProjectState } from "@/components/no-project-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Surface, SurfaceHeader } from "@/components/surface";
import { errorMessage } from "@/lib/api/errors";
import { useProjectStore } from "@/lib/project-store";

import { useUploadDocument, type UploadedDocument } from "../api";

const ACCEPTED = ".pdf,.docx,.xlsx,.csv";
const ACCEPTED_LABEL = "PDF, DOCX, XLSX or CSV";

export function DocumentsScreen() {
  const projectId = useProjectStore((s) => s.selectedProjectId);
  const upload = useUploadDocument();
  const [result, setResult] = React.useState<UploadedDocument | null>(null);
  const [objectUrl, setObjectUrl] = React.useState<string | null>(null);
  const [dragOver, setDragOver] = React.useState(false);
  const inputRef = React.useRef<HTMLInputElement>(null);

  // One object URL per result; revoke the previous one so uploading several files in a
  // row does not leak blob URLs for the lifetime of the tab.
  React.useEffect(() => {
    if (!result) return;
    const url = URL.createObjectURL(result.blob);
    setObjectUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [result]);

  function handleFile(file: File | undefined) {
    if (!file || !projectId) return;
    setResult(null);
    upload.mutate(
      { projectId, file },
      {
        onSuccess: (uploaded) => {
          setResult(uploaded);
          toast.success(`"${file.name}" protected. Download it below.`);
        },
        onError: (err) => toast.error(errorMessage(err)),
      },
    );
  }

  if (!projectId) {
    return (
      <div>
        <PageHeader title="Documents" description="Upload a document to scan and protect PII inside it." />
        <Surface>
          <NoProjectState />
        </Surface>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Documents"
        description={`Upload a ${ACCEPTED_LABEL} file. PIIShield scans it for PII and returns the SAME file, protected, in the same format (never a plain-text dump).`}
      />

      <Surface>
        <div
          className={`m-5 flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-12 text-center transition-colors ${
            dragOver ? "border-primary bg-primary-soft/40" : "border-border"
          }`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            handleFile(e.dataTransfer.files[0]);
          }}
        >
          <div className="flex size-11 items-center justify-center rounded-xl bg-primary-soft text-primary">
            <UploadCloudIcon className="size-5" />
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">Drag a file here, or choose one</p>
            <p className="mt-1 text-[12.5px] text-muted-foreground">{ACCEPTED_LABEL}</p>
          </div>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED}
            className="hidden"
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
          <Button variant="outline" onClick={() => inputRef.current?.click()} disabled={upload.isPending}>
            {upload.isPending ? "Uploading..." : "Choose file"}
          </Button>
        </div>
      </Surface>

      {result && objectUrl && (
        <Surface className="mt-4">
          <SurfaceHeader
            title="Protected file ready"
            titleExtra={
              <span className="flex items-center gap-1.5 text-[12px] font-medium text-savings">
                <CheckCircle2Icon className="size-3.5" />
                Protected
              </span>
            }
          />
          <div className="flex items-center justify-between gap-3 px-5 pb-5">
            <span className="truncate font-mono text-[12.5px] text-muted-foreground">{result.filename}</span>
            <Button variant="outline" render={<a href={objectUrl} download={result.filename} />}>
              <DownloadIcon />
              Download
            </Button>
          </div>
        </Surface>
      )}
    </div>
  );
}
