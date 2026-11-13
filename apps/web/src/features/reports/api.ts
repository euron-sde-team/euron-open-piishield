"use client";

import { useQuery } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import { qk, STALE } from "@/lib/query-keys";

/**
 * The summary report has no project_id query parameter in the OpenAPI document: it is
 * org-wide, scoped by the signed-in user's org via the bearer token, not by the
 * selected project. Called without params.
 */
export function useSummaryReport() {
  return useQuery({
    queryKey: qk.summary,
    queryFn: () => unwrap(api.GET("/api/v1/reports/summary")),
    staleTime: STALE.config,
  });
}
