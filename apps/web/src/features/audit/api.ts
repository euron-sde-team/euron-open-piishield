"use client";

import { useQuery } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import { qk, STALE } from "@/lib/query-keys";

export function useAuditLog(limit: number, action: string | undefined) {
  return useQuery({
    queryKey: qk.audit(limit, action),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/audit", {
          params: { query: { limit, ...(action ? { action } : {}) } },
        }),
      ),
    staleTime: STALE.live,
  });
}
