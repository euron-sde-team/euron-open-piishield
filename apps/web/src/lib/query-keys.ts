/**
 * Query keys in one place, so invalidation after a mutation names exactly what it
 * touched.
 */
export const qk = {
  projects: ["projects"] as const,
  project: (id: string) => ["projects", "detail", id] as const,
  policy: (projectId: string) => ["policy", projectId] as const,
  recognizers: (projectId: string) => ["recognizers", projectId] as const,
  keys: (projectId: string) => ["keys", projectId] as const,
  review: (projectId?: string) => ["review", projectId ?? null] as const,
  audit: (limit: number, action?: string) => ["audit", limit, action ?? null] as const,
  summary: ["reports", "summary"] as const,
  vaultGrants: ["vault", "grants"] as const,
} as const;

/** staleTime per kind of data, chosen deliberately. */
export const STALE = {
  config: 30_000,
  live: 5_000,
  static: 5 * 60_000,
} as const;
