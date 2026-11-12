"use client";

import { BoxesIcon } from "lucide-react";
import * as React from "react";

import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { CreateProjectDialog } from "@/features/projects/components/create-project-dialog";
import { useProjects } from "@/features/projects/api";

/**
 * Shared empty state for any screen that needs a selected project but has none yet,
 * either because the org has zero projects or because nothing is selected. Never a
 * dead end: offers the create-project action directly.
 */
export function NoProjectState() {
  const projects = useProjects();
  const [open, setOpen] = React.useState(false);
  const hasProjects = (projects.data?.length ?? 0) > 0;

  return (
    <>
      <EmptyState
        icon={BoxesIcon}
        title={hasProjects ? "Choose a project" : "Create your first project"}
        description={
          hasProjects
            ? "Pick a project from the switcher in the top bar to see its data here."
            : "Projects scope policies, API keys, scans and the vault. Create one to get started."
        }
        action={!hasProjects && <Button onClick={() => setOpen(true)}>New project</Button>}
      />
      <CreateProjectDialog open={open} onOpenChange={setOpen} />
    </>
  );
}
