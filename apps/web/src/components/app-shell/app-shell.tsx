"use client";

import { useRouter } from "next/navigation";
import * as React from "react";

import { ShieldMark } from "@/components/shield-logo";
import { useAuthStore } from "@/lib/auth-store";

import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";

/**
 * Dashboard chrome plus the session gate. PIIShield has no session cookie and no
 * /auth/me probe, so the gate is purely client side: wait for the persisted auth
 * store to rehydrate, then redirect to /login if there is no token. Nothing behind
 * this renders until that check completes, so a signed-out visitor never sees a
 * flash of the dashboard shell.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  // `useAuthStore.persist` only exists once the persist middleware has a working
  // storage backend, which is never true during the server render (no `localStorage`
  // there), so this must start false and only ever be read client side, inside an
  // effect.
  const [hydrated, setHydrated] = React.useState(false);
  const token = useAuthStore((s) => s.token);

  React.useEffect(() => {
    if (useAuthStore.persist.hasHydrated()) {
      setHydrated(true);
      return;
    }
    const unsub = useAuthStore.persist.onFinishHydration(() => setHydrated(true));
    return unsub;
  }, []);

  React.useEffect(() => {
    if (hydrated && !token) router.replace("/login");
  }, [hydrated, token, router]);

  if (!hydrated || !token) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-background" aria-busy>
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <ShieldMark className="size-10 animate-pulse" />
          <span className="text-[13px]">Loading PIIShield...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-dvh bg-background">
      <a
        href="#main"
        className="sr-only z-50 rounded-lg bg-card px-3 py-2 text-sm shadow-[var(--elev-3)] focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to content
      </a>
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main id="main" className="mx-auto w-full max-w-[1400px] flex-1 px-4 pt-4 pb-16 sm:px-6 lg:px-8">
          {children}
        </main>
      </div>
    </div>
  );
}
