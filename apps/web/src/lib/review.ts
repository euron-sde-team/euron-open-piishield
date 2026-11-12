import type { ReviewItem } from "./api/types";

/**
 * Defensive client filter: trust the API's own `status` filtering as primary, but if
 * it ever returns decided items too, the Review Queue should still show only pending
 * ones.
 */
export function pendingOnly(items: ReviewItem[]): ReviewItem[] {
  return items.filter((i) => i.status === "pending");
}

/** Sort newest first, for a stable, readable queue order. */
export function sortByCreatedDesc(items: ReviewItem[]): ReviewItem[] {
  return items.slice().sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
}
