"use client";

import { LockIcon, LogOutIcon, SettingsIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { Chip } from "@/components/ui/chip";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuthStore } from "@/lib/auth-store";
import { initials } from "@/lib/format";

export function UserMenu() {
  const user = useAuthStore((s) => s.user);
  const clearSession = useAuthStore((s) => s.clearSession);
  const router = useRouter();

  function signOut() {
    clearSession();
    toast.success("Signed out.");
    router.replace("/login");
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="Account menu"
        className="flex size-9 items-center justify-center rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span className="flex size-8 items-center justify-center rounded-full bg-gradient-to-br from-[var(--chart-1)] to-[var(--primary)] text-[12px] font-semibold text-white">
          {initials(user?.name)}
        </span>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-60">
        <DropdownMenuLabel className="pb-2">
          <div className="flex items-center justify-between gap-2">
            <span className="truncate text-[13px] font-semibold text-foreground">{user?.name ?? "Signed in"}</span>
            {user && <Chip tone="primary">{user.role}</Chip>}
          </div>
          <div className="truncate text-xs">{user?.email}</div>
          {user?.vault_access && (
            <div className="mt-1.5 flex items-center gap-1 text-[11px] font-medium text-savings">
              <LockIcon className="size-3" />
              Vault access
            </div>
          )}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => router.push("/settings")}>
          <SettingsIcon />
          Settings
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem variant="destructive" onClick={signOut}>
          <LogOutIcon />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
