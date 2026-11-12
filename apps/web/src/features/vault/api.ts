"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type { DetokenizeIn, VaultGrantIn } from "@/lib/api/types";
import { qk, STALE } from "@/lib/query-keys";

export function useVaultGrants(enabled: boolean) {
  return useQuery({
    queryKey: qk.vaultGrants,
    queryFn: () => unwrap(api.GET("/api/v1/vault/grants")),
    staleTime: STALE.config,
    enabled,
    retry: false,
  });
}

export function useCreateVaultGrant() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: VaultGrantIn) => unwrap(api.POST("/api/v1/vault/grants", { body })),
    onSuccess: () => void client.invalidateQueries({ queryKey: qk.vaultGrants }),
  });
}

export function useRevokeVaultGrant() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (grantId: string) => unwrap(api.DELETE("/api/v1/vault/grants/{grant_id}", { params: { path: { grant_id: grantId } } })),
    onSuccess: () => void client.invalidateQueries({ queryKey: qk.vaultGrants }),
  });
}

export function useDetokenize() {
  return useMutation({
    mutationFn: (body: DetokenizeIn) => unwrap(api.POST("/api/v1/vault/detokenize", { body })),
    retry: false,
  });
}
