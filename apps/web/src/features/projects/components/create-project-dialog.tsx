"use client";

import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, Textarea } from "@/components/ui/input";
import { Field, FieldError } from "@/components/ui/label";
import { errorMessage } from "@/lib/api/errors";
import { slugify } from "@/lib/format";
import { useProjectStore } from "@/lib/project-store";

import { useCreateProject } from "../api";

export function CreateProjectDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const create = useCreateProject();
  const setSelectedProjectId = useProjectStore((s) => s.setSelectedProjectId);
  const [name, setName] = React.useState("");
  const [slug, setSlug] = React.useState("");
  const [slugEdited, setSlugEdited] = React.useState(false);
  const [description, setDescription] = React.useState("");
  const [errors, setErrors] = React.useState<Record<string, string>>({});
  const [serverError, setServerError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (open) {
      setName("");
      setSlug("");
      setSlugEdited(false);
      setDescription("");
      setErrors({});
      setServerError(null);
    }
  }, [open]);

  function onNameChange(value: string) {
    setName(value);
    if (!slugEdited) setSlug(slugify(value));
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!name.trim()) errs.name = "Give the project a name.";
    const finalSlug = slug || slugify(name);
    if (!finalSlug || finalSlug.length < 2) {
      errs.slug = "Slug must be at least 2 characters, lowercase letters, digits and hyphens only.";
    }
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setServerError(null);
    create.mutate(
      { name: name.trim(), slug: finalSlug, description: description.trim() || undefined },
      {
        onSuccess: (project) => {
          toast.success(`Project "${project.name}" created.`);
          setSelectedProjectId(project.id);
          onOpenChange(false);
        },
        onError: (err) => setServerError(errorMessage(err)),
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !create.isPending && onOpenChange(o)}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>New project</DialogTitle>
          <DialogDescription>
            Projects scope policies, keys, scans and the vault. Pick a name; the slug is derived automatically.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="flex min-h-0 flex-col" noValidate>
          <DialogBody className="space-y-4">
            <Field label="Name" htmlFor="project-name" error={errors.name}>
              <Input id="project-name" value={name} onChange={(e) => onNameChange(e.target.value)} placeholder="Customer Support" autoFocus />
            </Field>
            <Field label="Slug" htmlFor="project-slug" error={errors.slug} hint="Lowercase letters, digits and hyphens.">
              <Input
                id="project-slug"
                value={slug}
                onChange={(e) => {
                  setSlugEdited(true);
                  setSlug(e.target.value);
                }}
                placeholder="customer-support"
                className="font-mono text-[12.5px]"
              />
            </Field>
            <Field label="Description" htmlFor="project-description" hint="Optional.">
              <Textarea
                id="project-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="What lives in this project"
                className="min-h-16"
              />
            </Field>
            {serverError && <FieldError>{serverError}</FieldError>}
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "Creating..." : "Create project"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
