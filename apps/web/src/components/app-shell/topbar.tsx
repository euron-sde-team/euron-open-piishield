"use client";

import { MenuIcon } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { ShieldLogo } from "@/components/shield-logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";

import { ProjectSwitcher } from "./project-switcher";
import { SidebarNav } from "./sidebar";
import { UserMenu } from "./user-menu";

export function Topbar() {
  const [menuOpen, setMenuOpen] = React.useState(false);

  return (
    <header className="sticky top-0 z-30 bg-background/80 backdrop-blur-md supports-[backdrop-filter]:bg-background/70">
      <div className="flex h-14 min-w-0 items-center gap-2 px-4 sm:px-6 lg:px-8">
        <Button variant="subtle" size="icon" className="-ml-2 shrink-0 lg:hidden" aria-label="Open navigation" onClick={() => setMenuOpen(true)}>
          <MenuIcon />
        </Button>
        <Link href="/" className="shrink-0 rounded-lg lg:hidden" aria-label="PIIShield home">
          <ShieldLogo />
        </Link>
        <ProjectSwitcher />
        <div className="ml-auto flex shrink-0 items-center gap-1">
          <ThemeToggle />
          <UserMenu />
        </div>
      </div>
      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        <SheetContent side="left" className="bg-sidebar">
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <div className="flex h-14 items-center px-4">
            <ShieldLogo />
          </div>
          <div className="overflow-y-auto px-3 pb-6">
            <SidebarNav onNavigate={() => setMenuOpen(false)} />
          </div>
        </SheetContent>
      </Sheet>
    </header>
  );
}
