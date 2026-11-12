"use client";

import { PlusIcon, Trash2Icon } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field, FieldError } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { errorMessage } from "@/lib/api/errors";

import { useCreateRecognizer, useDeleteRecognizer, useRecognizers } from "../api";

export function RecognizersPanel({ projectId }: { projectId: string }) {
  const recognizers = useRecognizers(projectId);
  const create = useCreateRecognizer(projectId);
  const remove = useDeleteRecognizer(projectId);
  const [name, setName] = React.useState("");
  const [category, setCategory] = React.useState("");
  const [pattern, setPattern] = React.useState("");
  const [confidence, setConfidence] = React.useState("0.7");
  const [error, setError] = React.useState<string | null>(null);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !category.trim() || !pattern.trim()) {
      setError("Name, category and pattern are required.");
      return;
    }
    try {
      new RegExp(pattern);
    } catch {
      setError("That is not a valid regular expression.");
      return;
    }
    const conf = Number(confidence);
    if (!Number.isFinite(conf) || conf < 0 || conf > 1) {
      setError("Confidence must be between 0 and 1.");
      return;
    }
    setError(null);
    create.mutate(
      { name: name.trim(), category: category.trim(), pattern: pattern.trim(), confidence: conf },
      {
        onSuccess: () => {
          toast.success(`Recognizer "${name}" added.`);
          setName("");
          setCategory("");
          setPattern("");
          setConfidence("0.7");
        },
        onError: (err) => setError(errorMessage(err)),
      },
    );
  }

  return (
    <div className="space-y-4">
      {recognizers.data && recognizers.data.length > 0 ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Category</TableHead>
              <TableHead>Pattern</TableHead>
              <TableHead>Confidence</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {recognizers.data.map((r) => (
              <TableRow key={r.id}>
                <TableCell className="font-medium">{r.name}</TableCell>
                <TableCell>{r.category}</TableCell>
                <TableCell className="max-w-56 truncate font-mono text-[12px] text-muted-foreground" title={r.pattern}>
                  {r.pattern}
                </TableCell>
                <TableCell className="tabular">{Math.round(r.confidence * 100)}%</TableCell>
                <TableCell>
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    aria-label={`Delete ${r.name}`}
                    onClick={() =>
                      remove.mutate(r.id, {
                        onSuccess: () => toast.success("Recognizer deleted."),
                        onError: (err) => toast.error(errorMessage(err)),
                      })
                    }
                  >
                    <Trash2Icon />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <p className="px-1 text-[13px] text-muted-foreground">
          No custom recognizers yet. Add one below to detect a pattern the built-in detectors miss.
        </p>
      )}

      <form onSubmit={submit} className="grid gap-3 rounded-xl bg-muted p-4 sm:grid-cols-4">
        <Field label="Name" htmlFor="rec-name">
          <Input id="rec-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Internal ticket ID" />
        </Field>
        <Field label="Category" htmlFor="rec-category">
          <Input id="rec-category" value={category} onChange={(e) => setCategory(e.target.value)} placeholder="custom" />
        </Field>
        <Field label="Pattern (regex)" htmlFor="rec-pattern" className="sm:col-span-2">
          <Input id="rec-pattern" value={pattern} onChange={(e) => setPattern(e.target.value)} placeholder="TCK-\\d{6}" className="font-mono text-[12.5px]" />
        </Field>
        <Field label="Confidence" htmlFor="rec-confidence">
          <Input id="rec-confidence" inputMode="decimal" value={confidence} onChange={(e) => setConfidence(e.target.value)} className="tabular" />
        </Field>
        <div className="flex items-end sm:col-span-3">
          {error && <FieldError>{error}</FieldError>}
        </div>
        <div className="flex items-end justify-end">
          <Button type="submit" disabled={create.isPending}>
            <PlusIcon />
            {create.isPending ? "Adding..." : "Add"}
          </Button>
        </div>
      </form>
    </div>
  );
}
