# @euron/piishield (Node.js)

The Node.js SDK for [Euron Open PIIShield](../../README.md), a self-hosted platform that
detects, masks, redacts, tokenizes and anonymizes personally identifiable and financial
information across text, JSON, documents, databases, and AI agent prompts and responses.
It is part of the open-source initiative of **ENGAGESPHERE TECHNOLOGY PRIVATE LIMITED**
and is MIT licensed.

This README is the canonical reference for the Node SDK: every method's signature, every
exception, the wire format it assumes, and the safety properties around tokenization and
the AI gateway. The Node SDK is deliberately minimal: the same primitives as
[the Python SDK](../python/README.md), without Python's extra convenience wrappers around
reports and policies beyond what the dashboard needs.

```bash
npm install @euron/piishield
```

The package is not on the npm registry yet (publishing is on the roadmap). Until then
install it from this repository, or point your `package.json` at the `sdks/node`
directory.

## Quickstart

```ts
import { PIIShield } from "@euron/piishield";

const shield = new PIIShield({
  apiUrl: "http://localhost:8000",
  apiKey: "YOUR_API_KEY",
  projectId: "YOUR_PROJECT_ID",
});

const text = "Customer: Rahul Sharma\nEmail: rahul@example.com\nPhone: 9876543210";
const result = await shield.mask(text);
console.log(result.protectedText);
```

```ts
// AI gateway: protect a prompt before it reaches an external model.
const protected_ = await shield.protect("My PAN is ABCDE1234F. Explain my tax record.");
// Send only protected_.protectedText to the external AI provider.
// protected_.scopeId stays with you: see "AI gateway safety property" below.
```

Every method is `async`/Promise based, which needs no special justification in Node:
there is no separate sync client the way the Python SDK has one.

## Installation requirements

Node.js 20 or newer (uses the global `fetch`, `FormData`, `AbortSignal.timeout`). No
runtime dependencies.

## Client construction

```ts
new PIIShield({
  apiUrl: string;
  apiKey: string;
  projectId: string;
  timeoutMs?: number;   // default 30000
  fetch?: (input: string, init: RequestInit) => Promise<Response>;   // default: global fetch
})
```

- `apiUrl`: the PIIShield API's base URL, for example `http://localhost:8000` (or
  `http://localhost:5530` against this project's own local Compose stack).
- `apiKey`: a project API key (`pii_<prefix>_<secret>`), created under
  `POST /api/v1/auth/keys` with `scope: "write"` for every call in this README except
  the read-only ones (`getPolicy`, `getAuditLogs`, `getReviewItems`), which also accept a
  `scope: "read"` key.
- `projectId`: the project this client acts on behalf of. Every call is scoped to it;
  an API key from one project can never read or act on another project's data (AC12).
- `fetch`: supply your own implementation for testing or for environments without a
  global `fetch`.

## Method reference

### Detection: `scan`, `scanJson`

```ts
shield.scan(text: string): Promise<ScanResult>
shield.scanJson(payload: unknown): Promise<ScanResult>
```

`scan` calls the dedicated `POST /api/v1/detectors/scan` route: detection only, no
protection applied, no policy enforcement, no audit entry written. Its findings have no
`method`/`placeholder`/`inReview` (always `""`/`null`/`false`), and `reviewCount` is
always `0`. `scanJson` has no dedicated route of its own: it calls `protect/json` with
every known category in `skip_categories`, so nothing is actually masked, only detected,
unless a category is required by the project's policy (AC10 forces protection on that
category regardless).

`ScanResult`:

| Property | Type | Meaning |
| --- | --- | --- |
| `findings` | `Finding[]` | every detected value (never the value itself) |
| `reviewCount` | `number` | how many findings were low-confidence and routed to review |
| `raw` | `Record<string, unknown>` | the unparsed response body |

`Finding` (matches `protection.schemas.ProtectedFindingOut` exactly):

| Property | Type | Meaning |
| --- | --- | --- |
| `category` | `string` | one of the five coarse categories every recognizer rolls up to: `"contact"`, `"credential"`, `"financial"`, `"government_id"`, `"personal"` (use these exact strings in `methodOverrides`/`skipCategories`) |
| `start`, `end` | `number` | the exact character offsets of the match |
| `confidence` | `number` | 0.0 to 1.0 |
| `checksumValid` | `boolean \| null` | set where a checksum applies (Luhn for cards, Verhoeff for Aadhaar, ISO 7064 mod 97 for IBAN); `null` otherwise |
| `recognizer` | `string` | which detector matched |
| `method` | `string` | the method actually applied: `"full_mask"`, `"partial_mask"`, `"redact"`, `"tokenize"`, `"skip"` (from `scan`) or `"review"` |
| `placeholder` | `string \| null` | the tokenize placeholder, set only when `method === "tokenize"` |
| `inReview` | `boolean` | `true` when routed to the review queue |

A `Finding` never carries the original matched value, by construction: there is no field
that could hold it, matching the server-side contract that the original value is
returned only by an authorized `detokenize` call.

### Protection: one flexible call, plus brief-exact wrappers

Same design as the Python SDK, kept consistent with it on purpose. The real API has one
protect endpoint per content type (no separate `/redact` or `/anonymize` route), so
`redact`/`anonymize`/`tokenize` are all built on `mask` with a different `method`:

```ts
shield.mask(text: string, options?: {
  method?: "full_mask" | "partial_mask" | "redact" | "tokenize";   // default "full_mask"
  categories?: string[];
  scopeId?: string;
}): Promise<ProtectionResult>

shield.maskJson(payload: unknown, options?: { ...same as mask }): Promise<ProtectionJsonResult>

shield.redact(text: string, categories?: string[]): Promise<ProtectionResult>
shield.anonymize(text: string, categories?: string[]): Promise<ProtectionResult>
shield.tokenize(text: string, options?: { scopeId?: string; categories?: string[] }): Promise<ProtectionResult>
```

`method` is applied as an override for every category named in `categories` (or every
detected category, if omitted); categories not named keep the project policy's own
configured method.

- `redact(text, categories)` == `mask(text, { method: "redact", categories })`
- `anonymize(text, categories)` == `mask(text, { method: "full_mask", categories })`
- `tokenize(text, options)` == `mask(text, { method: "tokenize", ...options })`

**The four methods** (AC3 of `docs/PLAN.md`; the server's literal values):

| `method` | Effect |
| --- | --- |
| `"full_mask"` | Replaces the whole value with a fixed mask. |
| `"partial_mask"` | Keeps the policy's configured reveal count of characters, masks the rest. |
| `"redact"` | Removes the value entirely, leaves `[REDACTED]`; no way to recover it from the response alone. |
| `"tokenize"` | Replaces the value with a stable placeholder (`[EMAIL_001]`); the real value exists only in the encrypted vault. |

`ProtectionResult`:

| Property | Type | Meaning |
| --- | --- | --- |
| `protectedText` | `string` | always safe to log, display or forward |
| `findings` | `Finding[]` | what was acted on |
| `reviewCount` | `number` | how many findings were routed to the review queue |
| `scopeId` | `string` | the scope used for placeholder consistency; always set (server-assigned when you did not pass one) |

`ProtectionJsonResult` is the same shape with `protectedJson: unknown` instead of
`protectedText: string`, preserving the exact input structure (AC7).

Both reject with `PolicyViolationError` when a protect call's internal `skip_categories`
usage (only `scan` uses this) would leave a required category unmasked (AC10).

### Tokenization scope consistency (AC4)

```ts
const first = await shield.tokenize("rahul@example.com", { scopeId: "checkout-session-42" });
const second = await shield.tokenize("rahul@example.com", { scopeId: "checkout-session-42" });
// first.protectedText === second.protectedText: same placeholder
```

Pass the same `scopeId` across calls to get placeholder consistency: the same input
value tokenized twice in one scope always yields the same placeholder, and two different
values never collide. Omit `scopeId` for a server-assigned scope (returned as
`result.scopeId`); pass that back on a later call to keep using it.

### `detokenize` and the vault permission model (AC5, AC6)

```ts
shield.detokenize(placeholder: string, scopeId: string): Promise<DetokenizeResult>
```

`detokenize` is the only call that can return an original sensitive value, and requires
the vault-access grant, separate from the base `apiKey`. The real backend models this as
a grant on an existing API key (`POST /api/v1/vault/grants`, owner role only), not a
second API key: once the grant exists for a given key, the same `PIIShield` client just
works for `detokenize`, no separate constructor option needed.

```ts
const result = await shield.detokenize("[EMAIL_001]", "checkout-session-42");
console.log(result.value); // the original email, restored
console.log(result.category); // "contact"
```

A caller whose key has no vault-access grant gets `VaultPermissionError` rejected on a
403 (server code `vault_access_required`), **never the original value and never a hint
of it** (AC5). `VaultPermissionError` extends `APIError`, so code that only catches
`APIError` still sees it:

```ts
import { VaultPermissionError } from "@euron/piishield";

try {
  const result = await shield.detokenize(placeholder, scopeId);
} catch (error) {
  if (error instanceof VaultPermissionError) {
    showRequestVaultAccessPrompt();
  } else {
    throw error;
  }
}
```

**The vault's encrypted mapping is never included in any response to a protect, document
or AI-gateway request** (AC6).

### AI gateway: `protect` and `restore` (AC9)

```ts
shield.protect(prompt: string, scopeId?: string): Promise<ProtectResult>
shield.restore(scopeId: string, modelResponseText: string): Promise<RestoreResult>
```

```ts
const protected_ = await shield.protect("My PAN is ABCDE1234F. Explain my tax record.");

// Send ONLY protected_.protectedText to the external model.
const modelResponse = await callExternalModel(protected_.protectedText);

// Restore placeholders in the model's response for your own application.
const restored = await shield.restore(protected_.scopeId, modelResponse);
console.log(restored.restoredText);   // the real PAN is back, for you only
```

#### AI gateway safety property

This is a real safety property, enforced structurally by the SDK's types:

- `ProtectResult.protectedText` (`string`) is the only field meant to leave your process
  and reach an external model.
- `ProtectResult.scopeId` (`string`) is a **separate property**. It is not embedded in
  `protectedText` and cannot be derived from it.
- `restore()` returns `RestoreResult.restoredText`, which is for **your calling
  application only**. The external model that produced the response text never sees it;
  nothing in this SDK sends it anywhere.
- Keep `scopeId` server side, or with the backend that called `protect`, never shipped to
  client-side code that also talks to the model provider.

Never spread or serialize the whole `ProtectResult` object toward the model provider;
only ever send `protected_.protectedText`.

### Documents: `protectFile`

```ts
shield.protectFile(content: Uint8Array | Blob, filename: string): Promise<Uint8Array>
```

Protects a PDF, DOCX, XLSX or CSV file and returns the protected file in the **same
format** (never a plain-text dump). `POST /api/v1/documents` returns the file as a raw
binary body, not JSON. Rejects with `UnsupportedFileTypeError` for an unrecognised
extension, before any request is sent.

### Database scan

```ts
shield.scanDatabase(
  connectionString: string,
  tableName: string,
  engine?: "postgres" | "mysql" | "sqlite",   // default "postgres"
  sampleRows?: number,                         // default 200
): Promise<DatabaseScanResult>
```

A read-only, column-level scan against a provided database connection. The connection
string is used once and never stored. 0.1.0 does not write back to or anonymize a live
database.

### Policies, audit logs, review queue

```ts
shield.getPolicy(): Promise<Policy>
shield.setPolicy(options?: {
  requiredCategories?: string[];
  maskingMethod?: Record<string, MaskingMethod>;
  partialMaskReveal?: number;
  confidenceThreshold?: number;
  retentionDays?: number;
}): Promise<Policy>

shield.getAuditLogs(options?: { limit?: number; action?: string }): Promise<AuditLogPage>
shield.getReviewItems(): Promise<ReviewItem[]>
shield.approveReviewItem(itemId: string): Promise<ReviewItem>
shield.dismissReviewItem(itemId: string): Promise<ReviewItem>
```

Policies are per-project, singular (`GET`/`PUT /api/v1/projects/{projectId}/policy`):
`setPolicy` always replaces the whole policy.

`AuditLogEntry` deliberately has no field that could hold an original value
(`findingCount` and `categories` only): the audit log records that a call happened,
never what it found (AC11).

## Exceptions

```
PIIShieldError                         base of every error this SDK throws
├── APIError                           PIIShield answered with a non-2xx error response
│   ├── VaultPermissionError           403 "vault_access_required" specifically on detokenize (AC5)
│   └── PolicyViolationError           422 "required_category_unmasked" (AC10)
└── PIIShieldConnectionError           PIIShield could not be reached, OR answered 503 "dependency_unavailable"

UnsupportedFileTypeError(PIIShieldError)   protectFile given an unrecognised extension
```

- **`PIIShieldError`**: catch broadly for "something went wrong talking to PIIShield."
- **`APIError`**: has `.message`, `.status`, `.code` and `.details`.
- **`VaultPermissionError`**: a 403 `vault_access_required`, from `detokenize`. Never
  carries the original value or a hint of it.
- **`PolicyViolationError`**: a 422 `required_category_unmasked`: a protect call was
  refused because a required category would be left unmasked.
- **`PIIShieldConnectionError`**: the request never got a response at all, or the server
  answered 503 `dependency_unavailable` (a dependency is down; the server's own contract
  is a clear, retryable failure, so this SDK treats both the same way).
- **`UnsupportedFileTypeError`**: raised client side before any request, when
  `protectFile` cannot infer a content type for the given filename.

## Wire format

**This section documents the HTTP request and response shapes this SDK uses**, confirmed
directly against the real `apps/api/src/piishield` source and a live running server, not
the product brief's own illustrative endpoint names. See the
[Python SDK's README](../python/README.md#wire-format) for the full endpoint table
(identical wire format, since both SDKs target the same API). In short:

- All requests carry `Authorization: Bearer <apiKey>` and
  `User-Agent: euron-piishield-node/<version>`.
- JSON bodies throughout; `protectFile` sends `multipart/form-data` with a `file` field
  and `projectId` as a query parameter, receiving the protected file as raw bytes.
- `scan` hits the dedicated `POST /api/v1/detectors/scan` (`{ findings, review_count }`,
  always `0`). `mask`/`redact`/`anonymize`/`tokenize`/`scanJson` hit
  `POST /api/v1/protect/text` (or `/protect/json`), differing only in
  `method_overrides`/`skip_categories`; that response shape is always
  `{ protected, findings, review_count, scope_id }`.
- `protect` returns `{ protected_prompt, findings, scope_id }`; `restore` returns
  `{ restored_response, placeholders_restored }`.
- Error bodies are `{ error: { code, type, message, details } }`; a 403 with code
  `vault_access_required` always becomes `VaultPermissionError`, a 422 with code
  `required_category_unmasked` always becomes `PolicyViolationError`, and a 503 always
  becomes `PIIShieldConnectionError`, regardless of endpoint.

## Development

```bash
pnpm install
pnpm test                 # mocked fetch, no network
TEST_API_URL=http://localhost:5530 TEST_API_KEY=... TEST_PROJECT_ID=... pnpm test:integration
pnpm lint
pnpm typecheck
pnpm build                # dist/ via tsc
```

The shared cross-language fixture at `../testdata/scan-fixture.json` is loaded by
`test/unit/fixture-parity.test.ts` to prove this SDK's response parsing agrees with the
Python SDK's (AC14 of `docs/PLAN.md`).
