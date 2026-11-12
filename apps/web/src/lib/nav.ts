import {
  BotIcon,
  DatabaseZapIcon,
  FileTextIcon,
  KeyRoundIcon,
  LayoutDashboardIcon,
  ListChecksIcon,
  LockIcon,
  ScanLineIcon,
  ScrollTextIcon,
  SettingsIcon,
  SlidersHorizontalIcon,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const NAV: NavGroup[] = [
  {
    label: "Protect",
    items: [
      { href: "/", label: "Overview", icon: LayoutDashboardIcon },
      { href: "/scan", label: "Scan Center", icon: ScanLineIcon },
      { href: "/review", label: "Review Queue", icon: ListChecksIcon },
    ],
  },
  {
    label: "Surfaces",
    items: [
      { href: "/documents", label: "Documents", icon: FileTextIcon },
      { href: "/database-scan", label: "Database Scan", icon: DatabaseZapIcon },
      { href: "/ai-gateway", label: "AI Gateway", icon: BotIcon },
    ],
  },
  {
    label: "Security",
    items: [
      { href: "/vault", label: "Token Vault", icon: LockIcon },
      { href: "/policies", label: "Policies", icon: SlidersHorizontalIcon },
      { href: "/keys", label: "API Keys", icon: KeyRoundIcon },
    ],
  },
  {
    label: "Organisation",
    items: [
      { href: "/audit", label: "Audit Log", icon: ScrollTextIcon },
      { href: "/settings", label: "Settings", icon: SettingsIcon },
    ],
  },
];

export const NAV_ITEMS: NavItem[] = NAV.flatMap((g) => g.items);

/** The nav item a path belongs to: exact match for "/", prefix match otherwise. */
export function activeNavItem(pathname: string): NavItem | undefined {
  const path = pathname.replace(/\/+$/, "") || "/";
  if (path === "/") return NAV_ITEMS.find((i) => i.href === "/");
  return NAV_ITEMS.filter((i) => i.href !== "/" && (path === i.href || path.startsWith(`${i.href}/`))).sort(
    (a, b) => b.href.length - a.href.length,
  )[0];
}

export function isActive(item: NavItem, pathname: string): boolean {
  return activeNavItem(pathname)?.href === item.href;
}
