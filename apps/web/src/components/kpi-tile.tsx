"use client";

import type { LucideIcon } from "lucide-react";
import * as React from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/cn";

/** Headline number tile for the overview KPIs: label, icon and a tabular value. */
export function KpiTile({
  label,
  value,
  icon: Icon,
  description,
  accent = "primary",
  loading = false,
}: {
  label: string;
  value: React.ReactNode;
  icon: LucideIcon;
  description?: React.ReactNode;
  accent?: "primary" | "savings" | "warning" | "danger";
  loading?: boolean;
}) {
  const iconTone = {
    primary: "bg-primary-soft text-primary",
    savings: "bg-savings-soft text-savings",
    warning: "bg-warning-soft text-warning",
    danger: "bg-danger-soft text-danger",
  }[accent];

  return (
    <div className="surface flex min-w-0 flex-col gap-3 p-4">
      <div className="flex items-center gap-2">
        <span className={cn("flex size-7 items-center justify-center rounded-lg", iconTone)}>
          <Icon className="size-3.5" />
        </span>
        <span className="min-w-0 truncate text-[12.5px] leading-tight font-medium text-muted-foreground">{label}</span>
      </div>
      {loading ? (
        <div className="space-y-2">
          <Skeleton className="h-7 w-20" />
          <Skeleton className="h-3.5 w-28" />
        </div>
      ) : (
        <div>
          <div className="truncate text-[24px] leading-none font-semibold tracking-[-0.02em] text-foreground tabular">{value}</div>
          {description && <div className="mt-2 truncate text-[11.5px] text-muted-foreground">{description}</div>}
        </div>
      )}
    </div>
  );
}
