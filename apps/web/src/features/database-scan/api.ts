"use client";

import { useMutation } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type { DatabaseScanIn } from "@/lib/api/types";

export function useDatabaseScan() {
  return useMutation({
    mutationFn: (body: DatabaseScanIn) => unwrap(api.POST("/api/v1/database-scan", { body })),
  });
}
