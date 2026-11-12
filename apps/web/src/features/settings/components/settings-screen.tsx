"use client";

import { LockIcon, LogOutIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { PageHeader } from "@/components/page-header";
import { Surface, SurfaceHeader } from "@/components/surface";
import { ThemeSelector } from "@/components/theme-toggle";
import { useAuthStore } from "@/lib/auth-store";
import { initials } from "@/lib/format";

export function SettingsScreen() {
  const user = useAuthStore((s) => s.user);
  const clearSession = useAuthStore((s) => s.clearSession);
  const router = useRouter();

  function signOut() {
    clearSession();
    toast.success("Signed out.");
    router.replace("/login");
  }

  return (
    <div>
      <PageHeader title="Settings" description="Your account and session." />

      <Surface>
        <SurfaceHeader title="Account" />
        <div className="flex items-center gap-4 px-5 pb-5">
          <span className="flex size-12 items-center justify-center rounded-full bg-gradient-to-br from-[var(--chart-1)] to-[var(--primary)] text-[15px] font-semibold text-white">
            {initials(user?.name)}
          </span>
          <div className="min-w-0">
            <div className="truncate text-[15px] font-semibold text-foreground">{user?.name ?? "Unknown"}</div>
            <div className="truncate text-[13px] text-muted-foreground">{user?.email}</div>
          </div>
        </div>
        <div className="grid gap-4 border-t border-hairline px-5 py-4 sm:grid-cols-3">
          <div>
            <div className="text-[11px] font-semibold tracking-wide text-faint uppercase">Organisation</div>
            <div className="mt-1 font-mono text-[12.5px] text-foreground">{user?.org_id ?? "-"}</div>
          </div>
          <div>
            <div className="text-[11px] font-semibold tracking-wide text-faint uppercase">Role</div>
            <div className="mt-1">
              <Chip tone="primary">{user?.role ?? "unknown"}</Chip>
            </div>
          </div>
          <div>
            <div className="text-[11px] font-semibold tracking-wide text-faint uppercase">Vault access</div>
            <div className="mt-1">
              {user?.vault_access ? (
                <Chip tone="savings" dot>
                  <LockIcon className="size-3" />
                  Granted
                </Chip>
              ) : (
                <Chip tone="neutral">Not granted</Chip>
              )}
            </div>
          </div>
        </div>
      </Surface>

      <Surface className="mt-4">
        <SurfaceHeader title="Appearance" description="Light, dark, or match your system." />
        <div className="px-5 pb-5">
          <ThemeSelector />
        </div>
      </Surface>

      <Surface className="mt-4">
        <SurfaceHeader title="Session" />
        <div className="px-5 pb-5">
          <Button variant="destructive-soft" onClick={signOut}>
            <LogOutIcon />
            Sign out
          </Button>
        </div>
      </Surface>
    </div>
  );
}
