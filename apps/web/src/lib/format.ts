/** First letters of up to two words, upper cased, for an avatar badge. */
export function initials(name: string | null | undefined): string {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  const first = parts[0]?.[0] ?? "";
  const last = parts.length > 1 ? parts[parts.length - 1]?.[0] ?? "" : "";
  return (first + last).toUpperCase();
}

/** A confidence (0 to 1) as a whole-number percent string, e.g. "87%". */
export function formatConfidence(value: number): string {
  return `${Math.round(value * 100)}%`;
}

/** Human label for a masking method code. */
export function methodLabel(method: string): string {
  const map: Record<string, string> = {
    full_mask: "Full mask",
    partial_mask: "Partial mask",
    redact: "Redact",
    tokenize: "Tokenize",
  };
  return map[method] ?? method.replace(/_/g, " ");
}

/** Human label for a free-form category key, e.g. "bank_account" -> "Bank account". */
export function categoryLabel(category: string): string {
  const spaced = category.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

/** Relative-ish, readable timestamp for tables and logs. */
export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Derive a valid project slug from a display name: lowercase, hyphenated, allowed chars only. */
export function slugify(name: string): string {
  const base = name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  const trimmed = base.length > 64 ? base.slice(0, 64).replace(/-+$/, "") : base;
  if (!trimmed) return "";
  // The pattern requires the slug to start with a letter or digit.
  return /^[a-z0-9]/.test(trimmed) ? trimmed : `p-${trimmed}`.slice(0, 64);
}
