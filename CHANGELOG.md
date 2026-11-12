# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - Unreleased

Initial release. See [docs/PLAN.md](docs/PLAN.md) for scope and acceptance criteria.

### Added

- **Detection**: regex recognizers with validated checksums for person name, email,
  phone (Indian and US/international), address, date of birth, PAN, Aadhaar, passport
  number, driving licence, credit/debit card, bank account number, IFSC, SWIFT/BIC, UPI
  ID, IBAN, US SSN, and generic credential patterns (API key, JWT, password assignment).
  Checksum validators: Luhn (cards), Verhoeff (Aadhaar), ISO 7064 mod 97 (IBAN), the PAN
  entity-character rule, and a US SSN area/group/serial sanity check. Every finding
  reports one of five coarse categories (`contact`, `credential`, `financial`,
  `government_id`, `personal`), the exact character span, a confidence score, and the
  checksum result where one applies. A value whose checksum fails is never reported as
  that category.
- A dedicated, side-effect-free detection route, `POST /api/v1/detectors/scan`, separate
  from the protect endpoints: detection only, no protection applied, no audit entry.
- A custom-pattern recognizer per project (`POST /api/v1/detectors/recognizers`).
- **Protection**: full masking, partial masking (configurable reveal count), redaction,
  and reversible tokenization with scope-consistent placeholders (the same value within
  one scope always yields the same placeholder; two different values never collide).
- **JSON protection**: recursive leaf-string scanning and protection that preserves the
  exact original structure (keys, nesting, array order).
- **Document protection**: PDF (text layer), DOCX, and XLSX/CSV scanning and protected
  re-export in the same file format, with a per-page/sheet findings breakdown. A document
  upload returns the protected file's raw bytes directly, never a JSON findings report.
- **The AI privacy gateway**: `POST /api/v1/ai-gateway/protect` (tokenizes every finding
  regardless of the project's masking policy, so the exact value can be restored later)
  and `POST /api/v1/ai-gateway/restore` (resolves placeholders back to their original
  values, scoped to the exact `scope_id` the calling application already holds; the
  gateway's `scope_id` is never embedded in the protected prompt sent to a model).
- **The vault**: envelope-encrypted tokenized values (AES-256-GCM, a per-record context
  binding to the vault entry's own id). Ships the `local` key backend
  (`KEY_MODE=local`); `KEY_MODE=kms` is an explicit, deliberate scope limit for 0.1.0
  (`core/sealing.py` raises `NotImplementedError` rather than silently falling back),
  with a KMS-backed `Sealer` behind the same protocol on the roadmap.
- **Vault access as a separate permission**: detokenizing a placeholder
  (`POST /api/v1/vault/detokenize`) requires an explicit grant
  (`POST /api/v1/vault/grants`, owner role only), never implied by the `owner` or `admin`
  role, nor by a write-scoped API key.
- **A read-only, column-level database scan** (`POST /api/v1/database-scan`) against a
  caller-supplied Postgres, MySQL or SQLite connection: samples rows and reports which
  columns look like they hold PII, with confidence, without writing back to or modifying
  the scanned database.
- **Policies**: per-project required categories, masking method per category, confidence
  threshold, and retention period, backed by a read-through policy snapshot cache
  (in-process TTL plus a KV version stamp). A protect call for a required category with
  masking disabled is refused with a clear error rather than silently passing the raw
  value through.
- **Review queue**: a finding below the confidence threshold is queued for a human
  decision (approve or dismiss) instead of being auto-protected or auto-ignored, unless
  its category is marked required, in which case it is protected and still queued for
  review.
- **Multi-tenant isolation**: `org_id` structural scoping on every table through a scoped
  repository; roles `owner`, `admin`, `viewer`; vault access as its own grant, independent
  of role. A cross-organisation lookup returns 404, never 403.
- **The append-only audit log**: every scan, mask, redact, tokenize, detokenize, policy
  change and vault-access change is recorded (who, when, how many findings, which
  categories), and the write path has no parameter through which an original value could
  ever be passed.
- **Dashboard (Next.js)**: sign in, Overview, Scan Center, Review Queue, Documents,
  Database Scan, AI Gateway, Token Vault, Policies, Audit Log, API Keys, Settings. Dark
  and light themes.
- **Admin API**: everything the dashboard does, under `/api/v1`, OpenAPI documented
  (`docs/api/openapi.yaml`, exported from the live FastAPI app).
- **SDKs**: Python and Node, both exposing `scan`, `mask`, `redact`, `tokenize`,
  `detokenize`, and the AI gateway's `protect`/`restore`, asserted byte-identical to the
  raw REST API by a shared test fixture.
- **CLI** (`piishield`): `serve` (the API), `migrate`, `revision`, `openapi`, `create-admin`,
  `seed-demo`. The same entry point serves the API and runs admin/ops tasks; there is no
  separate terminal scanning tool in 0.1.0 (use the API, a SDK, or the dashboard to scan).
- **Ops**: `/healthz`, `/readyz`, Prometheus `/metrics` (`piishield_scans_total`,
  `piishield_findings_total`, `piishield_protected_total`, `piishield_detokenize_total`),
  structured JSON logs, the append-only audit log.
- **Infrastructure as code**: Terraform modules for network, database, cache, storage,
  KMS, secrets, ECR, service and observability, with `local-floci` (applied automatically
  on `make up`), `aws-dev` and `aws-prod` environments.

### Known limitations

- `KEY_MODE=kms` is not implemented; only `KEY_MODE=local` ships in 0.1.0.
- The audit log is capped at 200 entries per request with no pagination past it
  (`next_cursor` is always `null`).
- No image OCR or scanned-document redaction; detection is regex and checksum based, not
  full NER.
- The 0.1.0 database scan is read-only and advisory; it does not write back to or
  anonymize the scanned database.
