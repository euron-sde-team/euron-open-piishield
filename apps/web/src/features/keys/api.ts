"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type { ApiKeyIn } from "@/lib/api/types";
import { qk, STALE } from "@/lib/query-keys";

export function useApiKeys(projectId: string | undefined) {
  return useQuery({
    queryKey: qk.keys(projectId ?? ""),
    queryFn: () => unwrap(api.GET("/api/v1/auth/keys", { params: { query: { project_id: projectId ?? "" } } })),
    staleTime: STALE.config,
    enabled: !!projectId,
  });
}

export function useCreateApiKey(projectId: string | undefined) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Omit<ApiKeyIn, "project_id">) => unwrap(api.POST("/api/v1/auth/keys", { body: { ...body, project_id: projectId ?? "" } })),
    onSuccess: () => void client.invalidateQueries({ queryKey: qk.keys(projectId ?? "") }),
  });
}

export function useRevokeApiKey(projectId: string | undefined) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (keyId: string) => unwrap(api.DELETE("/api/v1/auth/keys/{key_id}", { params: { path: { key_id: keyId } } })),
    onSuccess: () => void client.invalidateQueries({ queryKey: qk.keys(projectId ?? "") }),
  });
}
