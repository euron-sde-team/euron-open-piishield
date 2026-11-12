# Euron Open PIIShield 0.1.0: build plan

A self-hosted platform that detects, masks, redacts, tokenizes and anonymizes personally
identifiable and financial information across text, JSON, documents, databases, and AI
agent prompts and responses, so a developer never has to trust an external AI provider,
log aggregator or support tool with a customer's real name, card number, Aadhaar or PAN.

Source brief: the "Euron PIIShield: Complete Product Blueprint" (EuronSystems internal; 80
features across modules A to H). 0.1.0 is phases 1 to 5 of the brief's own roadmap
(detection, protection/masking, documents, API/SDK, the AI privacy gateway), deferring
phase 6 (full database scanning beyond a read-only column-level scan) and phase 7
(enterprise RBAC/compliance reporting beyond what 0.1.0 already needs for its own
multi-tenant safety) to the roadmap. Per this program's standing rules, licensed MIT (the
brief says Apache 2.0), the dashboard is Next.js (the brief says plain React), and the
detection engine is built in-house with validated checksums (the brief's own Microsoft
Presidio/spaCy/Tesseract suggestion is optional-dependency territory this program avoids
by default; OCR and NER are deferred to the roadmap rather than pulled in for 0.1.0).

## Purpose

A prompt that includes a real customer's PAN, card number or medical record number is not
unusual, it is the default: developers paste real data into AI tools, log real values in
application logs, and seed staging databases from production dumps, because redacting it
by hand is tedious and detection by hand is unreliable. **PIIShield's job is to make that
redaction automatic and provable**: send it text, a JSON payload, a document or a prompt,
and it returns the same content with every sensitive value found, classified and
protected by the method you chose, with a confidence score attached to every finding and
a hash-chained log of what was found and what was done to it, never the original value.

Comparable products: Microsoft Presidio (a detection library, not a platform: no API
server, no masking-method choice per field, no reversible vault, no AI-gateway framing),
AWS Comprehend PII/Macie (cloud-only, not self-hostable), commercial DLP suites (closed
source, not developer-first). PIIShield's angle: **one API for every surface** (text,
JSON, documents, an AI prompt/response gateway) instead of a detection library you wire up
yourself; **validated, checksummed detectors** (Luhn for cards, Verhoeff for Aadhaar, ISO
7064 mod 97 for IBAN, the PAN entity-character rule) so a 10-digit number is not treated as
a phone number just because it has 10 digits; and **reversible tokenization with the
mapping held in a separate encrypted vault that is never sent anywhere**, so an
authorized caller can restore the original value after an AI call without the AI provider
ever seeing it.

## Acceptance criteria (each is an automated test)

1. `make up` starts the whole system (Postgres, Redis, Floci, mock AI, api, web)
   with Terraform applied against Floci; a fresh API key can scan a text sample for PII
   within minutes of steps, with no other configuration.
2. Scanning a text sample containing a name, email, phone, PAN, Aadhaar, credit card
   number and a password-looking string returns one finding per value, each with its
   category, the exact span (start/end offset), a confidence score, and, where a checksum
   applies (card, Aadhaar, IBAN), whether it passed; a 10-digit string that is not a valid
   card or Aadhaar number by checksum is never reported as one.
3. Full masking, partial masking, redaction and tokenization each transform the same
   finding differently and correctly: full masking replaces the whole value with a fixed
   mask, partial masking keeps a configurable number of characters, redaction removes the
   value and leaves a `[REDACTED]` marker with no way to recover the original from the
   response alone, and tokenization replaces the value with a stable placeholder
   (`[EMAIL_001]`) while the real value exists only in the encrypted vault.
4. The same input value (e.g. the same email address) tokenized twice within one
   configured scope (a request, or a named session) always yields the same placeholder;
   two different values never collide on the same placeholder.
5. Detokenization returns the original value for a placeholder only to a caller with the
   vault-access permission, and a caller without it gets a 403, never the value and never
   a hint of it in the error.
6. The vault's encrypted mapping is never included in any response to a text, JSON,
   document or AI-gateway request; only a response to an explicit, authorized
   detokenization call ever returns an original value.
7. A JSON payload with nested objects and arrays is scanned at every string leaf, and the
   protected response preserves the exact original structure (same keys, same nesting,
   same array order), only leaf string values are changed.
8. A PDF, DOCX or XLSX/CSV upload returns a protected version of the same file format
   (not a plain-text dump), with every detected value masked, redacted or tokenized per
   the request, and the scan report lists what was found by page or sheet.
9. The AI privacy gateway protects a prompt before it would reach an external model,
   returns the protected prompt text plus a per-call token map, and a caller can submit
   the model's response for response-side scanning and optional restoration of
   placeholders back to the real values for the calling application only, never for the
   external model.
10. A policy can mark a data category (e.g. financial, government ID) as required to be
    masked, and a protect call for that category with masking disabled is refused with a
    clear error rather than silently passing the raw value through.
11. The audit log records every scan, mask, redact, tokenize and detokenize call (who,
    when, how many findings, which categories) but never the original sensitive value or
    the plaintext of a token mapping.
12. An API key from one organisation gets a 404, never another organisation's policies,
    vault entries, reports or audit records.
13. A detection confidence below a configured threshold is flagged for human review
    rather than auto-protected or auto-ignored, and the dashboard's review queue lists
    exactly those low-confidence findings.
14. The Python and Node SDKs produce byte-identical protected output to the same request
    made directly against the REST API (a shared fixture asserts this in both languages).

## Caching and query layers

| Layer | What | Where | Key | TTL / invalidation |
| --- | --- | --- | --- | --- |
| Project policy | Which categories are required/masking method per category | In-process TTL cache (5s) backed by a Redis version stamp | `cfg:v` counter | Any admin write bumps the version; every instance refreshes on next request |
| Tokenization scope map | Value-to-placeholder mapping for an in-flight request/session scope | Redis, short TTL matching the scope's own lifetime | scope id | Expires with the scope; the durable record lives in the vault table, not here |
| Detection regex/checksum tables | Compiled recognizer patterns per region | In-process, loaded once at startup | n/a | Process restart only; 0.1.0 has no hot-reload of custom patterns |
| Dashboard aggregates | Scan counts, findings by category, pending-review counts | Live Postgres aggregate query + Redis (or in-process memory) 15s response cache | query params | Computed on each cache miss; no separate rollup table or worker, see reports/service.py |
| Dashboard | Server state | TanStack Query | per resource | `staleTime` per view, invalidated on mutation |

## Scope

### In 0.1.0

| Area | What ships |
| --- | --- |
| Detection | Regex plus checksum validation (Luhn for cards, Verhoeff for Aadhaar, ISO 7064 mod 97 for IBAN, the PAN entity-character rule, a US SSN area/group sanity check) for: person name (dictionary/pattern-assisted, not full NER in 0.1.0), email, phone (Indian and US/international formats), address (pattern-assisted), date of birth, PAN, Aadhaar, passport number pattern, driving licence pattern, credit/debit card, bank account number pattern, IFSC, SWIFT/BIC, UPI ID, IBAN, US SSN, generic credential patterns (API key, JWT, password-assignment), a custom-pattern recognizer per project. Every finding carries category, span, confidence and checksum result. |
| Protection | Full masking, partial masking (configurable reveal count), redaction, reversible tokenization with scope-consistent placeholders. Format-preserving masking and synthetic data generation are roadmap. |
| Documents | PDF (text layer), DOCX, XLSX/CSV scanning and protected re-export in the same format. Image OCR and scanned-PDF redaction are roadmap (need an OCR dependency this program avoids pulling in for 0.1.0). |
| JSON | Recursive leaf-string scanning and protection preserving structure exactly. |
| AI privacy gateway | `protect` (before sending to any model) and `restore` (after, for the calling application only) endpoints; a per-call token map scoped to one request, never persisted longer than the policy's retention setting. |
| Database | A read-only, column-level scan against a provided connection (Postgres, MySQL, SQLite) that samples rows and reports which columns look like they hold PII, with confidence, for a human to act on; 0.1.0 does not write back to or anonymize a live database (that is the roadmap's bulk-anonymization feature, which needs its own safety review). |
| Vault | Envelope-encrypted (KMS or a local key), the only place an original value is ever recoverable from a token; detokenization is its own permission, separate from read access to everything else. |
| Policies | Per-project required categories, masking method per category, confidence threshold, retention period for scan records and vault entries. |
| Multi-tenant | `org_id` structural scoping on every table through a scoped repository, the same pattern as the program's other projects; roles owner, admin, viewer, plus a dedicated vault-access permission separate from admin. |
| Dashboard (Next.js) | Sign in, Overview, Scan Center (text/JSON/document), Detection categories, Policies, Token Vault (access-gated), Review Queue (low-confidence findings), AI Gateway, Database Scan, Audit Logs, Reports, Settings. Dark and light. |
| Admin API | Everything the dashboard does, under `/api/v1`, OpenAPI documented. |
| SDK | Python and Node, both exposing `scan`, `mask`, `redact`, `tokenize`, `detokenize`, and the AI-gateway `protect`/`restore` calls. |
| CLI | Scan a file or a folder from the terminal, print findings, optionally write a protected copy. |
| Ops | `/healthz`, `/readyz`, Prometheus `/metrics`, structured JSON logs, append-only audit log that never contains an original value. |
| IaC | Terraform modules: network, database, cache, storage, kms, secrets, ecr, service, observability. Envs: local-floci, aws-dev, aws-prod (validate only). |

### Roadmap (not 0.1.0)

Image OCR and scanned-document redaction, full NER-based name/address detection, database
write-back anonymization and bulk sanitization, GitHub/CI-CD scanning integrations,
format-preserving masking, synthetic data generation, consent tracking, SSO/OIDC for the
dashboard, a managed hosting offering.

## Request lifecycle (text/JSON/prompt path)

1. Authenticate the project API key; load its policy (required categories, masking
   method per category, confidence threshold) from the cached snapshot.
2. Run every enabled recognizer over the input; validate checksums where applicable;
   attach a confidence score per finding.
3. Drop findings below the confidence threshold into the review queue instead of
   protecting them automatically, unless the category is marked required (then it is
   protected regardless, per AC10, and still flagged for review).
4. Apply the requested or policy-default protection method per category: full mask,
   partial mask, redact, or tokenize (reserving a vault row and a scope-consistent
   placeholder for tokenize).
5. Return the protected text/JSON/document, the finding list (never the original values
   for a redacted or tokenized finding), and, for the AI gateway's `protect` call, a
   token map reference the same caller can later submit to `restore`.
6. Record the scan in the audit log (counts and categories, never values) and commit.

## Code layout (domain packages)

`core/` (config, db, redis, kms, errors, security, logging, deps) and one package per
domain: `auth`, `orgs`, `projects`, `detectors` (recognizers + checksums + scanning),
`protection` (masking/redaction/tokenization engines), `vault` (encrypted mapping store,
detokenization), `policies`, `documents` (PDF/DOCX/XLSX/CSV processors), `database_scan`,
`ai_gateway`, `review` (the low-confidence queue), `reports`, `audit`, `health`. Each has
router, schemas, service, repository, models. Backend architecture follows the program's
layering: router -> service -> repository -> models.

## Data model (Postgres, `org_id` structural tenant scoping)

`organizations`, `users`, `projects`, `api_keys`, `policies`, `recognizers` (custom
per-project patterns), `scan_events` (counts and categories only, append-only),
`findings` (metadata only outside an active request's lifetime; never a durable store of
the original value), `vault_entries` (encrypted value, placeholder, scope, category),
`review_items` (low-confidence findings pending a decision), `database_scan_results`,
`audit_log` (append-only).

## Ports (project 15)

web 5510, api 5530, postgres 5542, redis 5579, floci 5566, mailpit 5525, mock AI 5550,
tf-aws-on-floci 5596.

## Test plan

- Unit: every recognizer against known-good and known-bad samples (a Luhn-valid vs
  Luhn-invalid card number, a Verhoeff-valid vs invalid Aadhaar, a well-formed vs
  malformed IBAN, a 10-digit non-PII number correctly NOT flagged), each masking method's
  exact output shape, tokenization scope consistency, confidence thresholding, JSON
  leaf-recursion structure preservation.
- Integration (real Postgres, Redis, Floci, mock AI): every admin endpoint with RBAC;
  scan/mask/redact/tokenize/detokenize end to end; detokenize without the vault
  permission refused; a required category with masking disabled refused (AC10); document
  round-trip (PDF/DOCX/XLSX/CSV) preserves file format; the AI gateway protect-then-
  restore round trip; tenant isolation (a second org's key gets 404s); the audit log
  never contains an original value (a log/response scanner, matching the sibling
  projects' own secret-scanning test pattern).
- E2E (Playwright): sign in, scan a text sample in the Scan Center, see findings with
  confidence scores, choose a masking method and see the protected output, open the
  Token Vault and detokenize one value as an authorized user, open the Review Queue and
  act on a low-confidence finding, run the AI Gateway's protect/restore flow.
- Browser QA (Puppeteer): every page, light and dark, desktop and phone.

## Release verification (0.1.0)

Every acceptance criterion is proven by an automated test (integration tests run against
real Postgres, Redis, Floci and the mock AI service over HTTP; e2e against the full
Compose stack).

| # | Criterion | Proven by |
| --- | --- | --- |
| 1 | `make up` starts everything; first scan within minutes | Compose stack brought up from scratch; e2e `01-first-scan` |
| 2 | Checksummed, confidence-scored findings; no false-positive on an invalid checksum | `test_detectors.py::test_ac2_*` (one test per recognizer family) |
| 3 | Four protection methods produce correct, distinct output | `test_protection.py::test_ac3_*` (4 tests) |
| 4 | Scope-consistent tokenization, no placeholder collision | `test_vault.py::test_ac4_consistent_tokenization_within_scope` |
| 5 | Detokenization permission-gated | `test_vault.py::test_ac5_detokenize_requires_vault_permission` |
| 6 | Vault mapping never leaks into a scan/mask/redact/gateway response | `test_vault.py::test_ac6_mapping_never_in_response` |
| 7 | JSON structure preserved exactly | `test_protection.py::test_ac7_json_leaf_recursion_preserves_structure` |
| 8 | Document round-trip keeps file format | `test_documents.py::test_ac8_*` (PDF/DOCX/XLSX/CSV) |
| 9 | AI gateway protect/restore round trip | `test_ai_gateway.py::test_ac9_protect_then_restore` |
| 10 | Required category with masking off is refused | `test_policies.py::test_ac10_required_category_refuses_unmasked` |
| 11 | Audit log never contains an original value | `test_audit.py::test_ac11_audit_log_never_contains_a_real_value` |
| 12 | Tenant isolation | `test_tenancy.py::test_ac12_cross_org_404` |
| 13 | Low-confidence findings land in the review queue | `test_review.py::test_ac13_low_confidence_goes_to_review` |
| 14 | SDK parity with the raw API | `sdks/testdata` shared fixture, asserted in both `sdks/python` and `sdks/node` test suites |
