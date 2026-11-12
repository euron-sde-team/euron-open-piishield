/**
 * Errors the SDK throws. Every call either resolves to a typed result or rejects with one
 * of these. Catch `PIIShieldError` broadly, or a specific subclass (`VaultPermissionError`,
 * `PolicyViolationError`) when the caller needs to react differently.
 */

export class PIIShieldError extends Error {
  override name = "PIIShieldError";
}

/**
 * PIIShield answered with an error response: `{ error: { code, type, message, details } }`
 * (`piishield.core.errors.AppError.body`).
 */
export class APIError extends PIIShieldError {
  override name = "APIError";
  constructor(
    message: string,
    readonly status: number | null,
    readonly code: string,
    readonly details: Record<string, unknown> = {},
  ) {
    super(message);
  }
}

/**
 * `detokenize` was refused because the caller lacks the vault-access grant. Raised only
 * for a 403 with error code `vault_access_required`; never carries the original value or
 * a hint of it in `message` or `details`.
 */
export class VaultPermissionError extends APIError {
  override name = "VaultPermissionError";
}

/**
 * A protect call was refused because the project's policy marks a detected category as
 * required to be masked and the call would have left it unmasked (server code
 * `required_category_unmasked`, status 422). The whole call fails rather than silently
 * passing the raw value through for that category.
 */
export class PolicyViolationError extends APIError {
  override name = "PolicyViolationError";
}

/**
 * PIIShield could not be reached at all (network error, timeout, DNS failure), or a
 * dependency it needs (Postgres, Redis, the mock AI service) answered with a 503: the
 * server's own contract is a clear, retryable failure rather than a response that
 * silently omits findings, so this SDK surfaces both as the same connection-shaped error.
 */
export class PIIShieldConnectionError extends PIIShieldError {
  override name = "PIIShieldConnectionError";
}

/** `scanFile`/`protectFile` was given a file type PIIShield does not know how to scan. */
export class UnsupportedFileTypeError extends PIIShieldError {
  override name = "UnsupportedFileTypeError";
}
