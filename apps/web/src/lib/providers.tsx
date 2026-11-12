"use client";

import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import * as React from "react";
import { toast } from "sonner";

import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";

import { ApiError } from "./api/errors";
import { useAuthStore } from "./auth-store";
import { useProjectStore } from "./project-store";

let redirecting = false;

/**
 * Any 401 from a query or mutation ends the session in the UI: clear the bearer
 * token, one toast, then a hard navigation to /login. There is no /auth/me probe to
 * special-case: PIIShield has no such endpoint, so the first 401 on any call is what
 * decides the session is gone.
 */
function handleUnauthorized(err: unknown, client: QueryClient) {
  if (!(err instanceof ApiError) || err.status !== 401 || redirecting || typeof window === "undefined") return;
  if (window.location.pathname.startsWith("/login")) return;
  redirecting = true;
  client.clear();
  useAuthStore.getState().clearSession();
  toast.error("Your session expired. Sign in again.", { id: "session-expired" });
  window.location.assign("/login?reason=expired");
}

function makeClient(): QueryClient {
  const client: QueryClient = new QueryClient({
    queryCache: new QueryCache({
      onError: (err) => handleUnauthorized(err, client),
    }),
    mutationCache: new MutationCache({
      onError: (err) => handleUnauthorized(err, client),
    }),
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: true,
        retry: (count, err) => {
          // Client errors will not fix themselves; retry only network and 5xx, twice.
          if (err instanceof ApiError && err.status >= 400 && err.status < 500) return false;
          return count < 2;
        },
      },
      mutations: { retry: false },
    },
  });
  return client;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = React.useState(makeClient);

  React.useEffect(() => {
    void useAuthStore.persist.rehydrate();
    void useProjectStore.persist.rehydrate();
  }, []);

  return (
    <QueryClientProvider client={client}>
      <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
        <TooltipProvider>
          {children}
          <Toaster />
        </TooltipProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
