"use client";

import { useMutation } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type { GatewayProtectIn, GatewayRestoreIn } from "@/lib/api/types";

export function useGatewayProtect() {
  return useMutation({
    mutationFn: (body: GatewayProtectIn) => unwrap(api.POST("/api/v1/ai-gateway/protect", { body })),
  });
}

export function useGatewayRestore() {
  return useMutation({
    mutationFn: (body: GatewayRestoreIn) => unwrap(api.POST("/api/v1/ai-gateway/restore", { body })),
  });
}
