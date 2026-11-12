/**
 * The typed results of the PIIShield API. See the README's "Wire format" section. These
 * mirror the real wire format in apps/api/src/piishield: protection/schemas.py,
 * vault/schemas.py, ai_gateway/schemas.py, policies/schemas.py, audit/schemas.py,
 * database_scan/schemas.py, documents/schemas.py, review/schemas.py.
 */

export type MaskingMethod = "full_mask" | "partial_mask" | "redact" | "tokenize";

type Json = Record<string, unknown>;

function str(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function strOrNull(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function num(value: unknown, fallback = 0): number {
  return typeof value === "number" ? value : fallback;
}

function bool(value: unknown): boolean {
  return value === true;
}

function obj(value: unknown): Json {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Json) : {};
}

function list<T = unknown>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

/**
 * One detected value: what it is, where it is, how confident PIIShield is, and what was
 * done to it. Matches `protection.schemas.ProtectedFindingOut`.
 *
 * Never carries the original matched value: PIIShield returns the original only from an
 * authorized `detokenize` call, never from `protect`, a document, the AI gateway, or the
 * audit log.
 */
export class Finding {
  constructor(
    readonly category: string,
    readonly start: number,
    readonly end: number,
    readonly confidence: number,
    readonly checksumValid: boolean | null,
    readonly recognizer: string,
    readonly method: string,
    readonly placeholder: string | null,
    readonly inReview: boolean,
    readonly raw: Json,
  ) {}

  static fromApi(data: Json): Finding {
    return new Finding(
      str(data.category),
      num(data.start),
      num(data.end),
      num(data.confidence),
      typeof data.checksum_valid === "boolean" ? data.checksum_valid : null,
      str(data.recognizer),
      str(data.method),
      strOrNull(data.placeholder),
      bool(data.in_review),
      data,
    );
  }
}

function findings(value: unknown): Finding[] {
  return list<Json>(value).map((item) => Finding.fromApi(item));
}

/**
 * The result of `scan`: what was found, nothing changed. `scan` calls the dedicated
 * `POST /api/v1/detectors/scan` route: detection only, no protection applied and no
 * audit entry written, unlike `protect`/`mask`.
 */
export class ScanResult {
  constructor(
    readonly findings: Finding[],
    readonly reviewCount: number,
    readonly raw: Json,
  ) {}

  static fromApi(data: Json): ScanResult {
    return new ScanResult(findings(data.findings), num(data.review_count), data);
  }
}

/** The output of `mask`/`redact`/`anonymize`/`tokenize` on text. Matches
 * `protection.schemas.ProtectTextOut`. */
export class ProtectionResult {
  constructor(
    readonly protectedText: string,
    readonly findings: Finding[],
    readonly reviewCount: number,
    readonly scopeId: string,
    readonly raw: Json,
  ) {}

  static fromApi(data: Json): ProtectionResult {
    return new ProtectionResult(str(data.protected), findings(data.findings), num(data.review_count), str(data.scope_id), data);
  }
}

/**
 * The output of a `mask`/`redact`/`anonymize`/`tokenize` call on JSON. Matches
 * `protection.schemas.ProtectJsonOut`. `protectedJson` preserves the exact input
 * structure (same keys, nesting, array order); only leaf string values change (AC7).
 */
export class ProtectionJsonResult {
  constructor(
    readonly protectedJson: unknown,
    readonly findings: Finding[],
    readonly reviewCount: number,
    readonly scopeId: string,
    readonly raw: Json,
  ) {}

  static fromApi(data: Json): ProtectionJsonResult {
    return new ProtectionJsonResult(data.protected, findings(data.findings), num(data.review_count), str(data.scope_id), data);
  }
}

/**
 * The result of an authorized `detokenize` call. Matches `vault.schemas.DetokenizeOut`:
 * `{ placeholder, value, category }`. Only ever returned to a caller holding the
 * vault-access grant; everyone else gets `VaultPermissionError` instead of this object.
 */
export class DetokenizeResult {
  constructor(
    readonly placeholder: string,
    readonly value: string,
    readonly category: string,
    readonly raw: Json,
  ) {}

  static fromApi(data: Json): DetokenizeResult {
    return new DetokenizeResult(str(data.placeholder), str(data.value), str(data.category), data);
  }
}

/**
 * The output of the AI gateway's `protect` call. Matches `ai_gateway.schemas.GatewayProtectOut`.
 * `protectedText` is the only field meant to reach the external model; `scopeId` must
 * stay with the caller.
 */
export class ProtectResult {
  constructor(
    readonly protectedText: string,
    readonly scopeId: string,
    readonly findings: Finding[],
    readonly raw: Json,
  ) {}

  static fromApi(data: Json): ProtectResult {
    return new ProtectResult(str(data.protected_prompt), str(data.scope_id), findings(data.findings), data);
  }
}

/**
 * The output of the AI gateway's `restore` call. Matches `ai_gateway.schemas.GatewayRestoreOut`.
 * `restoredText` is for the calling application only: the external model that produced
 * the response text never sees it.
 */
export class RestoreResult {
  constructor(
    readonly restoredText: string,
    readonly placeholdersRestored: number,
    readonly raw: Json,
  ) {}

  static fromApi(data: Json): RestoreResult {
    return new RestoreResult(str(data.restored_response), num(data.placeholders_restored), data);
  }
}

/** A project's policy. Matches `policies.schemas.PolicyOut`. */
export class Policy {
  constructor(
    readonly id: string,
    readonly projectId: string,
    readonly requiredCategories: string[],
    readonly maskingMethod: Record<string, MaskingMethod>,
    readonly partialMaskReveal: number,
    readonly confidenceThreshold: number,
    readonly retentionDays: number,
    readonly raw: Json,
  ) {}

  static fromApi(data: Json): Policy {
    return new Policy(
      str(data.id),
      str(data.project_id),
      list<string>(data.required_categories),
      obj(data.masking_method) as Record<string, MaskingMethod>,
      num(data.partial_mask_reveal, 4),
      num(data.confidence_threshold, 0.6),
      num(data.retention_days, 90),
      data,
    );
  }
}

/** One row of the append-only audit log. Matches `audit.schemas.AuditEntryOut`. Never
 * carries an original sensitive value (AC11). */
export class AuditLogEntry {
  constructor(
    readonly id: string,
    readonly createdAt: string | null,
    readonly actorKind: string,
    readonly actorLabel: string,
    readonly action: string,
    readonly projectId: string | null,
    readonly findingCount: number,
    readonly categories: string[],
    readonly details: Json,
    readonly raw: Json,
  ) {}

  static fromApi(data: Json): AuditLogEntry {
    return new AuditLogEntry(
      str(data.id),
      strOrNull(data.created_at),
      str(data.actor_kind),
      str(data.actor_label),
      str(data.action),
      strOrNull(data.project_id),
      num(data.finding_count),
      list<string>(data.categories),
      obj(data.details),
      data,
    );
  }
}

/** A page of the audit log. Matches `audit.schemas.AuditPage`. */
export class AuditLogPage {
  constructor(
    readonly items: AuditLogEntry[],
    readonly nextCursor: string | null,
    readonly raw: Json,
  ) {}

  static fromApi(data: Json): AuditLogPage {
    const items = list<Json>(data.items).map((item) => AuditLogEntry.fromApi(item));
    return new AuditLogPage(items, strOrNull(data.next_cursor), data);
  }
}

/** One column's PII likelihood from a database scan. */
export class ColumnFinding {
  constructor(
    readonly column: string,
    readonly category: string,
    readonly confidence: number,
    readonly sampleHits: number,
  ) {}

  static fromApi(data: Json): ColumnFinding {
    return new ColumnFinding(str(data.column), str(data.category), num(data.confidence), num(data.sample_hits));
  }
}

/** A read-only, column-level scan of a provided database connection. Matches
 * `database_scan.schemas.DatabaseScanOut`. */
export class DatabaseScanResult {
  constructor(
    readonly id: string,
    readonly tableName: string,
    readonly rowsSampled: number,
    readonly columns: ColumnFinding[],
    readonly raw: Json,
  ) {}

  static fromApi(data: Json): DatabaseScanResult {
    const columns = list<Json>(data.columns).map((item) => ColumnFinding.fromApi(item));
    return new DatabaseScanResult(str(data.id), str(data.table_name), num(data.rows_sampled), columns, data);
  }
}

/** One pending low-confidence finding. Matches `review.schemas.ReviewItemOut`. */
export class ReviewItem {
  constructor(
    readonly id: string,
    readonly projectId: string,
    readonly category: string,
    readonly start: number,
    readonly end: number,
    readonly confidence: number,
    readonly recognizer: string,
    readonly alreadyProtected: boolean,
    readonly status: string,
    readonly createdAt: string | null,
    readonly decidedAt: string | null,
    readonly raw: Json,
  ) {}

  static fromApi(data: Json): ReviewItem {
    return new ReviewItem(
      str(data.id),
      str(data.project_id),
      str(data.category),
      num(data.start),
      num(data.end),
      num(data.confidence),
      str(data.recognizer),
      bool(data.already_protected),
      str(data.status),
      strOrNull(data.created_at),
      strOrNull(data.decided_at),
      data,
    );
  }
}
