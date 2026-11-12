/**
 * Client-side mirror of AC10: a required category with no configured masking method
 * will be refused by the API. This lets the Policies screen warn before submit instead
 * of round-tripping a guaranteed 4xx.
 */

export interface PolicyDraft {
  requiredCategories: string[];
  maskingMethod: Record<string, string>;
}

/** Required categories that have no entry in maskingMethod. */
export function unmaskedRequiredCategories(draft: PolicyDraft): string[] {
  return draft.requiredCategories.filter((c) => !draft.maskingMethod[c]);
}

/** Whether the draft would be accepted: every required category has a masking method. */
export function isPolicyDraftValid(draft: PolicyDraft): boolean {
  return unmaskedRequiredCategories(draft).length === 0;
}

/**
 * The real server-side categories, matching every Recognizer's category in
 * piishield.detectors.recognizers.RECOGNIZERS (confirmed live against the running API).
 * A policy's requiredCategories/maskingMethod keys must be one of these: the backend's
 * protection.service._effective_method looks up the finding's coarse category here, not
 * a per-recognizer name, so any other string (e.g. "email", "pan") never matches a real
 * finding and silently does nothing.
 */
const KNOWN_CATEGORIES = [
  "contact",
  "credential",
  "financial",
  "government_id",
  "personal",
] as const;

export type KnownCategory = (typeof KNOWN_CATEGORIES)[number];

export function knownCategories(): string[] {
  return [...KNOWN_CATEGORIES];
}

export const MASKING_METHODS = ["full_mask", "partial_mask", "redact", "tokenize"] as const;
