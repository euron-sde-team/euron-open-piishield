/**
 * `PIIShield`: detect, mask, redact, tokenize and anonymize PII; the AI gateway. Targets
 * the real routers in apps/api/src/piishield (protection, vault, ai_gateway, documents,
 * database_scan, policies, audit, review), not the product brief's own illustrative
 * endpoint names: see the README's "Wire format" section for the mapping.
 */

import { extname } from "node:path";

import {
  APIError,
  PIIShieldConnectionError,
  PolicyViolationError,
  UnsupportedFileTypeError,
  VaultPermissionError,
} from "./errors.js";
import {
  AuditLogPage,
  DatabaseScanResult,
  DetokenizeResult,
  type MaskingMethod,
  Policy,
  ProtectResult,
  ProtectionJsonResult,
  ProtectionResult,
  RestoreResult,
  ReviewItem,
  ScanResult,
} from "./models.js";

export const VERSION = "0.1.0";
const USER_AGENT = `euron-piishield-node/${VERSION}`;

const CONTENT_TYPE_BY_EXTENSION: Record<string, string> = {
  ".pdf": "application/pdf",
  ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  ".csv": "text/csv",
};

// The real server-side categories, matching every Recognizer's category in
// piishield.detectors.recognizers.RECOGNIZERS (confirmed live against the running API).
// Used as method_overrides/skip_categories keys. An earlier version of this list used
// per-recognizer names ("email", "pan", "credit_card", ...), which never matched any
// finding's real category server side (protection.service._effective_method looks up
// overrides.get(category, ...) against the coarse category, not the recognizer name), so
// every mask/tokenize/redact/anonymize call silently fell through to the project's own
// policy default for that category instead of applying the method the caller asked for.
const ALL_CATEGORIES = ["contact", "credential", "financial", "government_id", "personal"];

type Json = Record<string, unknown>;
export type FetchLike = (input: string, init: RequestInit) => Promise<Response>;

export interface PIIShieldOptions {
  /** PIIShield's API, for example `http://localhost:8000`. */
  apiUrl: string;
  apiKey: string;
  /** The project this client acts on behalf of; every call is scoped to it. */
  projectId: string;
  /** Per-request timeout in milliseconds. Default 30000. */
  timeoutMs?: number;
  /** A fetch implementation (default: the global fetch). */
  fetch?: FetchLike;
}

function checkOptions(apiUrl: string, apiKey: string): string {
  if (!/^https?:\/\//.test(apiUrl)) {
    throw new RangeError("apiUrl must be an http(s) URL, for example http://localhost:8000");
  }
  if (!apiKey) {
    throw new RangeError("apiKey is required (create one under a project's API keys)");
  }
  return apiUrl.replace(/\/+$/, "");
}

function guessContentType(filename: string): string {
  const ext = extname(filename).toLowerCase();
  const contentType = CONTENT_TYPE_BY_EXTENSION[ext];
  if (!contentType) {
    const supported = Object.keys(CONTENT_TYPE_BY_EXTENSION).sort().join(", ");
    throw new UnsupportedFileTypeError(
      `Cannot tell the content type for ${JSON.stringify(filename)}: pass filename explicitly, ` +
        `or use one of the supported extensions (${supported})`,
    );
  }
  return contentType;
}

async function errorFrom(response: Response): Promise<APIError> {
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  const data = (body && typeof body === "object" ? body : {}) as Json;
  const err = (data.error && typeof data.error === "object" ? data.error : {}) as Json;
  const code = typeof err.code === "string" ? err.code : "api_error";
  const message = typeof err.message === "string" ? err.message : response.statusText || "error";
  const details = (err.details && typeof err.details === "object" ? err.details : {}) as Json;

  if (response.status === 403 && code === "vault_access_required") {
    return new VaultPermissionError(message, response.status, code, details);
  }
  if (response.status === 422 && code === "required_category_unmasked") {
    return new PolicyViolationError(message, response.status, code, details);
  }
  return new APIError(message, response.status, code, details);
}

function transportError(error: unknown): PIIShieldConnectionError {
  const name = error instanceof Error ? error.name : "Error";
  const message = error instanceof Error ? error.message : String(error);
  return new PIIShieldConnectionError(`Could not reach PIIShield: ${name}: ${message}`);
}

function list<T = unknown>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function methodOverrides(method: MaskingMethod, categories: string[] | undefined): Record<string, MaskingMethod> {
  const overrides: Record<string, MaskingMethod> = {};
  for (const category of categories ?? ALL_CATEGORIES) overrides[category] = method;
  return overrides;
}

/**
 * A connection to a self-hosted PIIShield API, scoped to one project.
 *
 * ```ts
 * const shield = new PIIShield({ apiUrl: "http://localhost:8000", apiKey: "YOUR_API_KEY", projectId: "..." });
 * const result = await shield.mask("Email: rahul@example.com");
 * console.log(result.protectedText);
 * ```
 */
export class PIIShield {
  readonly apiUrl: string;
  readonly apiKey: string;
  readonly projectId: string;
  readonly timeoutMs: number;
  readonly #fetch: FetchLike;

  constructor(options: PIIShieldOptions) {
    this.apiUrl = checkOptions(options.apiUrl, options.apiKey);
    this.apiKey = options.apiKey;
    this.projectId = options.projectId;
    this.timeoutMs = options.timeoutMs ?? 30_000;
    this.#fetch = options.fetch ?? ((input, init) => fetch(input, init));
  }

  async #send(
    method: string,
    path: string,
    options: { body?: unknown; query?: Record<string, string>; form?: FormData } = {},
  ): Promise<Response> {
    const headers: Record<string, string> = { Authorization: `Bearer ${this.apiKey}`, "User-Agent": USER_AGENT };
    const init: RequestInit = { method, headers };
    if (options.form) {
      init.body = options.form;
    } else if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(options.body);
    }
    const query = options.query ? `?${new URLSearchParams(options.query).toString()}` : "";
    let response: Response;
    try {
      response = await this.#fetch(`${this.apiUrl}${path}${query}`, { ...init, signal: AbortSignal.timeout(this.timeoutMs) });
    } catch (error) {
      throw transportError(error);
    }
    if (response.status >= 300) {
      const error = await errorFrom(response);
      if (response.status === 503) throw new PIIShieldConnectionError(error.message);
      throw error;
    }
    return response;
  }

  async #request(
    method: string,
    path: string,
    options: { body?: unknown; query?: Record<string, string>; form?: FormData } = {},
  ): Promise<Json> {
    const response = await this.#send(method, path, options);
    const text = await response.text();
    return text ? (JSON.parse(text) as Json) : {};
  }

  // Detection

  /**
   * Detect PII in plain text without protecting it. `POST /api/v1/detectors/scan`: a
   * dedicated, side-effect-free detection route (no protection applied, no policy
   * enforcement, no audit entry written, unlike `protect`/`mask`). Findings from this
   * route always have `method: ""`, `placeholder: null`, `inReview: false` and
   * `reviewCount: 0`, since nothing is ever masked.
   */
  async scan(text: string): Promise<ScanResult> {
    const body = { project_id: this.projectId, text };
    const data = await this.#request("POST", "/api/v1/detectors/scan", { body });
    return ScanResult.fromApi(data);
  }

  /** `scan`'s JSON counterpart: detects at every string leaf without protecting. */
  async scanJson(payload: unknown): Promise<ScanResult> {
    const body = { project_id: this.projectId, payload, skip_categories: ALL_CATEGORIES };
    const data = await this.#request("POST", "/api/v1/protect/json", { body });
    return ScanResult.fromApi(data);
  }

  // Protection: one flexible call plus brief-exact convenience wrappers (see README).

  /**
   * Protect text with one of four methods. `POST /api/v1/protect/text`. `method`
   * defaults to `"full_mask"` and is applied as an override for every category named in
   * `categories` (or every detected category, if omitted); categories not named keep
   * the project policy's own configured method.
   */
  async mask(text: string, options: { method?: MaskingMethod; categories?: string[]; scopeId?: string } = {}): Promise<ProtectionResult> {
    const body: Json = {
      project_id: this.projectId,
      text,
      method_overrides: methodOverrides(options.method ?? "full_mask", options.categories),
    };
    if (options.scopeId !== undefined) body.scope_id = options.scopeId;
    const data = await this.#request("POST", "/api/v1/protect/text", { body });
    return ProtectionResult.fromApi(data);
  }

  /** `mask`'s JSON counterpart: protects every string leaf, preserves structure (AC7). */
  async maskJson(
    payload: unknown,
    options: { method?: MaskingMethod; categories?: string[]; scopeId?: string } = {},
  ): Promise<ProtectionJsonResult> {
    const body: Json = {
      project_id: this.projectId,
      payload,
      method_overrides: methodOverrides(options.method ?? "full_mask", options.categories),
    };
    if (options.scopeId !== undefined) body.scope_id = options.scopeId;
    const data = await this.#request("POST", "/api/v1/protect/json", { body });
    return ProtectionJsonResult.fromApi(data);
  }

  /** `mask(text, { method: "redact", categories })`. */
  redact(text: string, categories?: string[]): Promise<ProtectionResult> {
    return this.mask(text, categories ? { method: "redact", categories } : { method: "redact" });
  }

  /** `mask(text, { method: "full_mask", categories })`, named for brief parity (the
   * brief's `/anonymize` endpoint does not exist separately on the real API). */
  anonymize(text: string, categories?: string[]): Promise<ProtectionResult> {
    return this.mask(text, categories ? { method: "full_mask", categories } : { method: "full_mask" });
  }

  /**
   * `mask(text, { method: "tokenize", scopeId })`. Pass the same `scopeId` across calls
   * for placeholder consistency (AC4): the same input value tokenized twice in one
   * scope always yields the same placeholder. Omit it and the server assigns a
   * call-local scope, returned as `result.scopeId`.
   */
  tokenize(text: string, options: { scopeId?: string; categories?: string[] } = {}): Promise<ProtectionResult> {
    const maskOptions: { method: MaskingMethod; categories?: string[]; scopeId?: string } = { method: "tokenize" };
    if (options.categories !== undefined) maskOptions.categories = options.categories;
    if (options.scopeId !== undefined) maskOptions.scopeId = options.scopeId;
    return this.mask(text, maskOptions);
  }

  /**
   * Restore the original value behind one tokenize placeholder.
   * `POST /api/v1/vault/detokenize`. Requires the vault-access grant, a separate
   * permission from the base API key, granted per user or per key with
   * `POST /api/v1/vault/grants` (owner only). Rejects with `VaultPermissionError` on a
   * 403, never a redacted or empty value and never a hint of the original in the error
   * (AC5, AC6).
   */
  async detokenize(placeholder: string, scopeId: string): Promise<DetokenizeResult> {
    const body = { project_id: this.projectId, placeholder, scope_id: scopeId };
    const data = await this.#request("POST", "/api/v1/vault/detokenize", { body });
    return DetokenizeResult.fromApi(data);
  }

  // AI gateway

  /**
   * Protect a prompt before it reaches an external model. `POST /api/v1/ai-gateway/protect`.
   * Send only `result.protectedText` to the external AI provider; keep `result.scopeId`
   * server side or caller side. See the README's "AI gateway safety property".
   */
  async protect(prompt: string, scopeId?: string): Promise<ProtectResult> {
    const body: Json = { project_id: this.projectId, prompt };
    if (scopeId !== undefined) body.scope_id = scopeId;
    const data = await this.#request("POST", "/api/v1/ai-gateway/protect", { body });
    return ProtectResult.fromApi(data);
  }

  /**
   * Restore placeholders in a model's response, for the calling application only.
   * `POST /api/v1/ai-gateway/restore`. The external model never sees the result.
   */
  async restore(scopeId: string, modelResponseText: string): Promise<RestoreResult> {
    const body = { project_id: this.projectId, scope_id: scopeId, model_response: modelResponseText };
    const data = await this.#request("POST", "/api/v1/ai-gateway/restore", { body });
    return RestoreResult.fromApi(data);
  }

  // Documents

  /**
   * Protect a PDF, DOCX, XLSX or CSV file, returned as the SAME file format (never a
   * plain-text dump). `POST /api/v1/documents`. Returns the raw protected file bytes.
   */
  async protectFile(content: Uint8Array | Blob, filename: string): Promise<Uint8Array> {
    guessContentType(filename); // validated client side; the server infers it too
    const form = new FormData();
    const blob = content instanceof Blob ? content : new Blob([content.slice().buffer]);
    form.append("file", blob, filename);
    const response = await this.#send("POST", "/api/v1/documents", { form, query: { project_id: this.projectId } });
    return new Uint8Array(await response.arrayBuffer());
  }

  // Database scan

  /**
   * A read-only, column-level scan against a provided database connection.
   * `POST /api/v1/database-scan`. `engine` is one of `"postgres"`, `"mysql"` or
   * `"sqlite"`. Samples `sampleRows` rows of `tableName`. The connection string is used
   * once and never stored. Never writes back to the database.
   */
  async scanDatabase(
    connectionString: string,
    tableName: string,
    engine: "postgres" | "mysql" | "sqlite" = "postgres",
    sampleRows = 200,
  ): Promise<DatabaseScanResult> {
    const body = { project_id: this.projectId, engine, connection_string: connectionString, table_name: tableName, sample_rows: sampleRows };
    const data = await this.#request("POST", "/api/v1/database-scan", { body });
    return DatabaseScanResult.fromApi(data);
  }

  // Policies, audit logs, review queue

  /** `GET /api/v1/projects/{projectId}/policy`: this project's policy. */
  async getPolicy(): Promise<Policy> {
    const data = await this.#request("GET", `/api/v1/projects/${this.projectId}/policy`);
    return Policy.fromApi(data);
  }

  /** `PUT /api/v1/projects/{projectId}/policy`: replace this project's policy. */
  async setPolicy(options: {
    requiredCategories?: string[];
    maskingMethod?: Record<string, MaskingMethod>;
    partialMaskReveal?: number;
    confidenceThreshold?: number;
    retentionDays?: number;
  } = {}): Promise<Policy> {
    const body = {
      required_categories: options.requiredCategories ?? [],
      masking_method: options.maskingMethod ?? {},
      partial_mask_reveal: options.partialMaskReveal ?? 4,
      confidence_threshold: options.confidenceThreshold ?? 0.6,
      retention_days: options.retentionDays ?? 90,
    };
    const data = await this.#request("PUT", `/api/v1/projects/${this.projectId}/policy`, { body });
    return Policy.fromApi(data);
  }

  /** `GET /api/v1/audit`: a page of the append-only audit log. Never contains an
   * original sensitive value (AC11). */
  async getAuditLogs(options: { limit?: number; action?: string } = {}): Promise<AuditLogPage> {
    const query: Record<string, string> = { limit: String(options.limit ?? 50) };
    if (options.action !== undefined) query.action = options.action;
    const data = await this.#request("GET", "/api/v1/audit", { query });
    return AuditLogPage.fromApi(data);
  }

  /** `GET /api/v1/review`: pending low-confidence findings for this project. */
  async getReviewItems(): Promise<ReviewItem[]> {
    const response = await this.#send("GET", "/api/v1/review", { query: { project_id: this.projectId } });
    const text = await response.text();
    const data: unknown = text ? JSON.parse(text) : [];
    return list<Json>(data).map((item) => ReviewItem.fromApi(item));
  }

  /** `POST /api/v1/review/{itemId}/approve`. */
  async approveReviewItem(itemId: string): Promise<ReviewItem> {
    const data = await this.#request("POST", `/api/v1/review/${encodeURIComponent(itemId)}/approve`, { body: {} });
    return ReviewItem.fromApi(data);
  }

  /** `POST /api/v1/review/{itemId}/dismiss`. */
  async dismissReviewItem(itemId: string): Promise<ReviewItem> {
    const data = await this.#request("POST", `/api/v1/review/${encodeURIComponent(itemId)}/dismiss`, { body: {} });
    return ReviewItem.fromApi(data);
  }
}
