/**
 * Named aliases over the generated OpenAPI types (`pnpm gen:api`). Nothing here is
 * hand-written: every shape comes from `schema.d.ts`, which is generated from
 * docs/api/openapi.yaml.
 */
import type { components, operations } from "./schema";

type S = components["schemas"];

export type User = S["UserOut"];
export type Session = S["SessionOut"];
export type LoginIn = S["LoginIn"];
export type SignupIn = S["SignupIn"];

export type Project = S["ProjectOut"];
export type ProjectIn = S["ProjectIn"];
export type ProjectUpdate = S["ProjectUpdate"];

export type Policy = S["PolicyOut"];
export type PolicyIn = S["PolicyIn"];
export type MaskingMethod = "full_mask" | "partial_mask" | "redact" | "tokenize";

export type ApiKey = S["ApiKeyOut"];
export type ApiKeyCreated = S["ApiKeyCreated"];
export type ApiKeyIn = S["ApiKeyIn"];
export type ApiKeyScope = NonNullable<ApiKeyIn["scope"]>;

export type Finding = S["FindingOut"];
export type ScanResult = S["ScanResultOut"];
export type ScanTextIn = S["ScanTextIn"];

export type ProtectedFinding = S["ProtectedFindingOut"];
export type ProtectTextIn = S["ProtectTextIn"];
export type ProtectTextOut = S["ProtectTextOut"];
export type ProtectJsonIn = S["ProtectJsonIn"];
export type ProtectJsonOut = S["ProtectJsonOut"];

export type CustomRecognizer = S["CustomRecognizerOut"];
export type CustomRecognizerIn = S["CustomRecognizerIn"];

export type DatabaseScanIn = S["DatabaseScanIn"];
export type DatabaseScanOut = S["DatabaseScanOut"];
export type ColumnFinding = S["ColumnFinding"];
export type DbEngine = DatabaseScanIn["engine"];

export type GatewayProtectIn = S["GatewayProtectIn"];
export type GatewayProtectOut = S["GatewayProtectOut"];
export type GatewayRestoreIn = S["GatewayRestoreIn"];
export type GatewayRestoreOut = S["GatewayRestoreOut"];

export type DetokenizeIn = S["DetokenizeIn"];
export type DetokenizeOut = S["DetokenizeOut"];
export type VaultGrant = S["VaultGrantOut"];
export type VaultGrantIn = S["VaultGrantIn"];

export type ReviewItem = S["ReviewItemOut"];

export type AuditEntry = S["AuditEntryOut"];
export type AuditPage = S["AuditPage"];

export type SummaryReport = S["SummaryReport"];
export type CategoryCount = S["CategoryCount"];

export type ReviewListParams = NonNullable<operations["list_pending_api_v1_review_get"]["parameters"]["query"]>;
export type AuditListParams = NonNullable<operations["list_audit_api_v1_audit_get"]["parameters"]["query"]>;
