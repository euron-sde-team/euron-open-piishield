"use client";

import { DatabaseZapIcon } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { NoProjectState } from "@/components/no-project-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field, FieldHint } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { SimpleSelect } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Surface, SurfaceHeader } from "@/components/surface";
import { errorMessage } from "@/lib/api/errors";
import type { DbEngine } from "@/lib/api/types";
import { categoryLabel, formatConfidence } from "@/lib/format";
import { useProjectStore } from "@/lib/project-store";

import { useDatabaseScan } from "../api";

const ENGINES: { value: DbEngine; label: string }[] = [
  { value: "postgres", label: "PostgreSQL" },
  { value: "mysql", label: "MySQL" },
  { value: "sqlite", label: "SQLite" },
];

export function DatabaseScanScreen() {
  const projectId = useProjectStore((s) => s.selectedProjectId);
  const scan = useDatabaseScan();
  const [engine, setEngine] = React.useState<DbEngine>("postgres");
  const [connectionString, setConnectionString] = React.useState("");
  const [tableName, setTableName] = React.useState("");
  const [sampleRows, setSampleRows] = React.useState("200");
  const [errors, setErrors] = React.useState<Record<string, string>>({});

  if (!projectId) {
    return (
      <div>
        <PageHeader title="Database Scan" description="Sample a table's columns to find PII, read-only." />
        <Surface>
          <NoProjectState />
        </Surface>
      </div>
    );
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!projectId) return;
    const errs: Record<string, string> = {};
    if (!connectionString.trim()) errs.connection = "Enter a connection string.";
    if (!tableName.trim()) errs.table = "Enter a table name.";
    const n = Number(sampleRows);
    if (!Number.isInteger(n) || n < 1 || n > 5000) errs.rows = "Whole number from 1 to 5000.";
    setErrors(errs);
    if (Object.keys(errs).length) return;

    scan.mutate(
      { project_id: projectId, engine, connection_string: connectionString.trim(), table_name: tableName.trim(), sample_rows: n },
      {
        onSuccess: (result) => toast.success(`Sampled ${result.rows_sampled} row(s) from ${result.table_name}.`),
        onError: (err) => toast.error(errorMessage(err)),
      },
    );
  }

  return (
    <div>
      <PageHeader title="Database Scan" description="Column-level sampling for PII, nothing is modified or anonymized in place." />

      <Surface>
        <SurfaceHeader
          title="Connect and sample"
          description="This is read-only sampling. It reports which columns look like they hold PII and how confident it is, it does not change or anonymize anything in the database."
        />
        <form onSubmit={submit} className="space-y-4 px-5 pb-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Engine" htmlFor="db-engine">
              <SimpleSelect
                id="db-engine"
                value={engine}
                onValueChange={(v) => setEngine(v as DbEngine)}
                options={ENGINES}
              />
            </Field>
            <Field label="Table name" htmlFor="db-table" error={errors.table}>
              <Input id="db-table" value={tableName} onChange={(e) => setTableName(e.target.value)} placeholder="customers" />
            </Field>
          </div>
          <Field label="Connection string" htmlFor="db-conn" error={errors.connection} hint="Masked because it may contain credentials.">
            <Input
              id="db-conn"
              type="password"
              value={connectionString}
              onChange={(e) => setConnectionString(e.target.value)}
              placeholder="postgresql://user:pass@host:5432/db"
              className="font-mono text-[12.5px]"
              autoComplete="off"
            />
          </Field>
          <Field label="Sample rows" htmlFor="db-rows" error={errors.rows}>
            <Input id="db-rows" inputMode="numeric" className="tabular w-32" value={sampleRows} onChange={(e) => setSampleRows(e.target.value)} />
            <FieldHint>1 to 5000 rows.</FieldHint>
          </Field>
          <Button type="submit" disabled={scan.isPending}>
            <DatabaseZapIcon />
            {scan.isPending ? "Sampling..." : "Scan table"}
          </Button>
        </form>
      </Surface>

      {scan.data && (
        <Surface className="mt-4">
          <SurfaceHeader
            title={`Columns in ${scan.data.table_name}`}
            description={`${scan.data.rows_sampled} row(s) sampled.`}
          />
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Column</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Confidence</TableHead>
                <TableHead>Sample hits</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {scan.data.columns.map((c, i) => (
                <TableRow key={i}>
                  <TableCell className="font-medium font-mono text-[12.5px]">{c.column}</TableCell>
                  <TableCell>{categoryLabel(c.category)}</TableCell>
                  <TableCell className="w-40">
                    <div className="flex items-center gap-2">
                      <Progress value={c.confidence * 100} tone={c.confidence > 0.75 ? "danger" : c.confidence > 0.5 ? "warning" : "primary"} className="w-20" />
                      <span className="tabular text-[12.5px] text-muted-foreground">{formatConfidence(c.confidence)}</span>
                    </div>
                  </TableCell>
                  <TableCell className="tabular">{c.sample_hits}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Surface>
      )}
    </div>
  );
}
