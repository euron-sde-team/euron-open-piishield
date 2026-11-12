/**
 * Euron Open PIIShield for Node.js.
 *
 * ```ts
 * import { PIIShield } from "@euron/piishield";
 *
 * const shield = new PIIShield({ apiUrl: "http://localhost:8000", apiKey: "YOUR_API_KEY", projectId: "..." });
 * const result = await shield.mask("Email: rahul@example.com");
 * console.log(result.protectedText);
 * ```
 *
 * See the README for the full wire format, every exception type, and the vault-scope and
 * AI-gateway safety properties.
 */

export { PIIShield, VERSION, type FetchLike, type PIIShieldOptions } from "./client.js";
export {
  APIError,
  PIIShieldConnectionError,
  PIIShieldError,
  PolicyViolationError,
  UnsupportedFileTypeError,
  VaultPermissionError,
} from "./errors.js";
export {
  AuditLogEntry,
  AuditLogPage,
  ColumnFinding,
  DatabaseScanResult,
  DetokenizeResult,
  Finding,
  Policy,
  ProtectResult,
  ProtectionJsonResult,
  ProtectionResult,
  RestoreResult,
  ReviewItem,
  ScanResult,
  type MaskingMethod,
} from "./models.js";
