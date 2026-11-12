"use client";

import { Chip, type chipVariants } from "@/components/ui/chip";
import type { VariantProps } from "class-variance-authority";

type Tone = NonNullable<VariantProps<typeof chipVariants>["tone"]>;

/** Status chip for a review item's lifecycle state. */
export function ReviewStatusChip({ status }: { status: string | null | undefined }) {
  const s = (status ?? "").toLowerCase();
  const spec: { tone: Tone; label: string } =
    s === "approved"
      ? { tone: "savings", label: "Approved" }
      : s === "dismissed"
        ? { tone: "neutral", label: "Dismissed" }
        : { tone: "warning", label: "Pending" };
  return (
    <Chip tone={spec.tone} dot>
      {spec.label}
    </Chip>
  );
}

/** Chip for a masking method, so the same method always reads the same color. */
export function MethodChip({ method }: { method: string }) {
  const tones: Record<string, Tone> = {
    full_mask: "neutral",
    partial_mask: "info",
    redact: "danger",
    tokenize: "primary",
  };
  const labels: Record<string, string> = {
    full_mask: "Full mask",
    partial_mask: "Partial mask",
    redact: "Redact",
    tokenize: "Tokenize",
  };
  return (
    <Chip tone={tones[method] ?? "neutral"}>{labels[method] ?? method}</Chip>
  );
}

/** Chip for a scope (read / write) on an API key. */
export function ScopeChip({ scope }: { scope: string }) {
  return <Chip tone={scope === "write" ? "primary" : "neutral"}>{scope}</Chip>;
}
