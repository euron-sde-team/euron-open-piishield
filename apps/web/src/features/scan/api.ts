"use client";

import { useMutation } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type { ProtectJsonIn, ProtectTextIn, ScanTextIn } from "@/lib/api/types";

export function useScanText() {
  return useMutation({
    mutationFn: (body: ScanTextIn) => unwrap(api.POST("/api/v1/detectors/scan", { body })),
  });
}

export function useProtectText() {
  return useMutation({
    mutationFn: (body: ProtectTextIn) => unwrap(api.POST("/api/v1/protect/text", { body })),
  });
}

export function useProtectJson() {
  return useMutation({
    mutationFn: (body: ProtectJsonIn) => unwrap(api.POST("/api/v1/protect/json", { body })),
  });
}
