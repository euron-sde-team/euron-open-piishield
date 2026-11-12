"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type { LoginIn, SignupIn } from "@/lib/api/types";
import { useAuthStore } from "@/lib/auth-store";

export function useLogin() {
  const client = useQueryClient();
  const setSession = useAuthStore((s) => s.setSession);
  return useMutation({
    mutationFn: (body: LoginIn) => unwrap(api.POST("/api/v1/auth/login", { body })),
    onSuccess: (session) => {
      client.clear();
      setSession(session);
    },
  });
}

export function useSignup() {
  const client = useQueryClient();
  const setSession = useAuthStore((s) => s.setSession);
  return useMutation({
    mutationFn: (body: SignupIn) => unwrap(api.POST("/api/v1/auth/signup", { body })),
    onSuccess: (session) => {
      client.clear();
      setSession(session);
    },
  });
}
