"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import { qk, STALE } from "@/lib/query-keys";

export function useReviewQueue(projectId: string | undefined) {
  return useQuery({
    queryKey: qk.review(projectId),
    // Omit project_id entirely when nothing is selected rather than sending an empty
    // string: the API rejects "" with a UUID-parsing validation error.
    queryFn: () => unwrap(api.GET("/api/v1/review", projectId ? { params: { query: { project_id: projectId } } } : undefined)),
    staleTime: STALE.live,
    enabled: !!projectId,
  });
}

export function useApproveReview(projectId: string | undefined) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (itemId: string) => unwrap(api.POST("/api/v1/review/{item_id}/approve", { params: { path: { item_id: itemId } } })),
    onSuccess: () => void client.invalidateQueries({ queryKey: qk.review(projectId) }),
  });
}

export function useDismissReview(projectId: string | undefined) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (itemId: string) => unwrap(api.POST("/api/v1/review/{item_id}/dismiss", { params: { path: { item_id: itemId } } })),
    onSuccess: () => void client.invalidateQueries({ queryKey: qk.review(projectId) }),
  });
}
