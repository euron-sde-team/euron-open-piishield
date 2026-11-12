"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type { Project, ProjectIn, ProjectUpdate } from "@/lib/api/types";
import { useAuthStore } from "@/lib/auth-store";
import { qk, STALE } from "@/lib/query-keys";

export function useProjects() {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: qk.projects,
    queryFn: () => unwrap(api.GET("/api/v1/projects")),
    staleTime: STALE.config,
    enabled: !!token,
  });
}

export function useProject(id: string | undefined) {
  const client = useQueryClient();
  return useQuery({
    queryKey: qk.project(id ?? ""),
    queryFn: () => unwrap(api.GET("/api/v1/projects/{project_id}", { params: { path: { project_id: id ?? "" } } })),
    staleTime: STALE.config,
    enabled: !!id,
    initialData: () => client.getQueryData<Project[]>(qk.projects)?.find((p) => p.id === id),
    initialDataUpdatedAt: () => client.getQueryState(qk.projects)?.dataUpdatedAt,
  });
}

export function useCreateProject() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: ProjectIn) => unwrap(api.POST("/api/v1/projects", { body })),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: qk.projects });
    },
  });
}

export function useUpdateProject() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: ProjectUpdate }) =>
      unwrap(api.PATCH("/api/v1/projects/{project_id}", { params: { path: { project_id: id } }, body })),
    onSuccess: (project) => {
      client.setQueryData(qk.project(project.id), project);
      void client.invalidateQueries({ queryKey: qk.projects });
    },
  });
}
