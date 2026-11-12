"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import type { User } from "./api/types";

/**
 * The bearer session. PIIShield has no session cookie: the API returns a JWT on
 * login/signup and every other call carries `Authorization: Bearer <token>`. This
 * store is the only place that token lives, persisted to localStorage so a reload
 * keeps the person signed in.
 */
interface AuthState {
  token: string | null;
  user: User | null;
  setSession: (session: { token: string; user: User }) => void;
  clearSession: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      setSession: ({ token, user }) => set({ token, user }),
      clearSession: () => set({ token: null, user: null }),
    }),
    {
      name: "piishield.auth",
      version: 1,
      skipHydration: true,
      storage: createJSONStorage(() => localStorage),
      partialize: (s) => ({ token: s.token, user: s.user }),
    },
  ),
);

/** Read the current token without a React subscription (for the fetch middleware). */
export function getAuthToken(): string | null {
  return useAuthStore.getState().token;
}
