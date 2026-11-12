"use client";

import { ChevronsUpDownIcon, PlusIcon } from "lucide-react";
import * as React from "react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useProjects } from "@/features/projects/api";
import { CreateProjectDialog } from "@/features/projects/components/create-project-dialog";
import { useProjectStore } from "@/lib/project-store";

/**
 * Lists every project in the org and persists the selection. Every other screen
 * reads `selectedProjectId` from the store, so this is the one place a project is
 * chosen.
 */
export function ProjectSwitcher() {
  const projects = useProjects();
  const selectedProjectId = useProjectStore((s) => s.selectedProjectId);
  const setSelectedProjectId = useProjectStore((s) => s.setSelectedProjectId);
  const [createOpen, setCreateOpen] = React.useState(false);

  // Default to the first project once the list loads, if nothing is selected yet,
  // or if the stored id no longer exists in this org.
  React.useEffect(() => {
    if (!projects.data) return;
    const stillExists = projects.data.some((p) => p.id === selectedProjectId);
    if ((!selectedProjectId || !stillExists) && projects.data.length > 0) {
      setSelectedProjectId(projects.data[0]?.id ?? null);
    }
  }, [projects.data, selectedProjectId, setSelectedProjectId]);

  const selected = projects.data?.find((p) => p.id === selectedProjectId);

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger
          aria-label="Switch project"
          className="flex h-9 max-w-[140px] min-w-0 items-center gap-2 rounded-lg bg-muted px-3 text-[13px] font-medium text-foreground outline-none hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring sm:max-w-[220px]"
        >
          <span className="min-w-0 truncate">
            {projects.isLoading ? "Loading..." : selected ? selected.name : "No project"}
          </span>
          <ChevronsUpDownIcon className="size-3.5 shrink-0 text-muted-foreground" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-64">
          <DropdownMenuLabel>Projects</DropdownMenuLabel>
          {(projects.data ?? []).map((p) => (
            <DropdownMenuItem key={p.id} onClick={() => setSelectedProjectId(p.id)}>
              <span className="truncate">{p.name}</span>
            </DropdownMenuItem>
          ))}
          {projects.data?.length === 0 && (
            <div className="px-2.5 py-2 text-[12.5px] text-muted-foreground">No projects yet.</div>
          )}
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => setCreateOpen(true)}>
            <PlusIcon />
            New project
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <CreateProjectDialog open={createOpen} onOpenChange={setCreateOpen} />
    </>
  );
}
