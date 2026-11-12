"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type { CustomRecognizerIn, PolicyIn } from "@/lib/api/types";
import { qk, STALE } from "@/lib/query-keys";

export function usePolicy(projectId: string | undefined) {
  return useQuery({
    queryKey: qk.policy(projectId ?? ""),
    queryFn: () => unwrap(api.GET("/api/v1/projects/{project_id}/policy", { params: { path: { project_id: projectId ?? "" } } })),
    staleTime: STALE.config,
    enabled: !!projectId,
  });
}

export function useUpdatePolicy(projectId: string | undefined) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: PolicyIn) =>
      unwrap(api.PUT("/api/v1/projects/{project_id}/policy", { params: { path: { project_id: projectId ?? "" } }, body })),
    onSuccess: (policy) => {
      client.setQueryData(qk.policy(projectId ?? ""), policy);
    },
  });
}

export function useRecognizers(projectId: string | undefined) {
  return useQuery({
    queryKey: qk.recognizers(projectId ?? ""),
    queryFn: () => unwrap(api.GET("/api/v1/detectors/recognizers", { params: { query: { project_id: projectId ?? "" } } })),
    staleTime: STALE.config,
    enabled: !!projectId,
  });
}

export function useCreateRecognizer(projectId: string | undefined) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Omit<CustomRecognizerIn, "project_id">) =>
      unwrap(api.POST("/api/v1/detectors/recognizers", { body: { ...body, project_id: projectId ?? "" } })),
    onSuccess: () => void client.invalidateQueries({ queryKey: qk.recognizers(projectId ?? "") }),
  });
}

export function useDeleteRecognizer(projectId: string | undefined) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (recognizerId: string) =>
      unwrap(api.DELETE("/api/v1/detectors/recognizers/{recognizer_id}", { params: { path: { recognizer_id: recognizerId } } })),
    onSuccess: () => void client.invalidateQueries({ queryKey: qk.recognizers(projectId ?? "") }),
  });
}
