# Security Policy

PIIShield detects and protects personally identifiable and financial information, and
holds an encrypted vault of the original values behind any tokenized placeholder, so we
take reports seriously and respond quickly.

## Supported versions

| Version | Supported |
| --- | --- |
| 0.x (latest minor) | Yes |
| Older minors | No |

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Report privately through GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
on this repository ("Security" tab, "Report a vulnerability").

Please include:

- the affected component (`apps/api`, `apps/web`, `sdks/python`, `sdks/node`,
  `infra/terraform/...`) and version or commit,
- a description of the issue and its impact,
- steps to reproduce, or a proof of concept,
- any suggested mitigation.

What to expect:

| Stage | Target |
| --- | --- |
| Acknowledgement | within 3 business days |
| Initial assessment and severity | within 7 business days |
| Fix or mitigation for critical and high issues | within 30 days |
| Coordinated public disclosure | after a fix is released, credited to you unless you prefer otherwise |

## Scope

In scope: the code in this repository and the infrastructure it provisions with its
default settings. We are especially interested in:

- any way to recover a tokenized value from the vault, the database, or an API response
  without the vault-access permission,
- any way for a request authenticated as one organisation to read, modify or detokenize
  another organisation's projects, policies, vault entries, scans, reports or audit
  records,
- any way for a scan, mask, redact, tokenize, document, database-scan or AI gateway
  response, or the audit log, to contain an original sensitive value,
- any way to bypass a policy's required-category masking (a protect call for a required
  category with masking disabled must be refused, never silently pass the raw value
  through),
- authentication or authorization bypasses in the dashboard or the admin API,
- a way to recover an API key's secret, a session, or the vault master key from the API,
  logs or database.

Out of scope:

- **The demo seed.** `make demo` creates a well-known demo password
  (`Demo-Owner-Pass-1`) on purpose, published in this repository's own documentation.
- **The mock AI service** (`apps/api/src/mockai`), a test and demo fixture, never deployed
  to AWS.
- **`key_mode=kms` not being implemented.** This is a documented, deliberate scope
  limit of 0.1.0 (`core/sealing.py build_sealer` raises `NotImplementedError` for it on
  purpose, rather than silently weakening to a different backend), not a vulnerability.
  See [docs/architecture/adr/0001-envelope-encryption-local-key-only.md](docs/architecture/adr/0001-envelope-encryption-local-key-only.md).
- **The audit log's 200-entry cap with no pagination past it.** A documented 0.1.0
  limitation (see [docs/architecture/security.md](docs/architecture/security.md)), not a
  confidentiality issue: no data is lost, only unreachable through that endpoint past the
  cap.
- **Detection gaps from missing OCR or full NER.** 0.1.0's recognizers are regex and
  checksum based, with no image OCR and no full named-entity recognition; an undetected
  value in a scanned image or an unusual free-text name format is a known, documented
  roadmap item (see [docs/architecture/threat-model.md](docs/architecture/threat-model.md)),
  not a vulnerability report.
- Findings that require a compromised host, a compromised AWS account, or leaked
  deployment secrets.
- Denial of service through resource exhaustion of a deployment you operate yourself.

## What this product actually protects, so a report can be evaluated accurately

- **The vault.** Every tokenized value is encrypted with AES-256-GCM under a per-record
  context binding (the vault entry's own id), so a ciphertext copied between rows fails to
  decrypt. 0.1.0 ships one key backend, `key_mode=local` (a master key from the
  environment); `key_mode=kms` is roadmap, not shipped.
- **Vault access** is a permission independent of role and of API key scope: an `owner`,
  an `admin`, and a write-scoped API key do not get it automatically. It is a separate
  grant (`POST /api/v1/vault/grants`, owner role required).
- **The AI gateway's `restore`** is a different trust boundary from the vault's
  `detokenize`: it resolves placeholders only within the exact `scope_id` a caller's own
  earlier `protect` call returned, and that `scope_id` is never embedded in the prompt sent
  to the external model. See
  [docs/architecture/security.md](docs/architecture/security.md).
- **Tenant isolation** is structural: every table carries `org_id`, every query is scoped,
  and a cross-organisation lookup returns 404, never 403, never a hint that the row
  exists.
- **The audit log** cannot carry a raw value by construction: `audit.service.record` has no
  parameter a raw value could be passed through, and a sanitizer drops any detail key that
  looks like it could hold one.

Read the full design in [docs/architecture/security.md](docs/architecture/security.md) and
[docs/architecture/threat-model.md](docs/architecture/threat-model.md) before filing a
report, so the report can focus on where the actual design differs from the actual code,
not on a misunderstanding of what 0.1.0 claims to do.

## Hardening checklist for operators

- Set a real `LOCAL_MASTER_KEY`, `SESSION_SECRET` and `API_KEY_PEPPER` (32+ random
  characters, never a default) before running with `ENVIRONMENT=production`; the boot
  guard refuses to start otherwise. See
  [docs/guides/configuration.md](docs/guides/configuration.md).
- Set `COOKIE_SECURE=true` and a real `CORS_ORIGINS` allowlist (never `*`) in production;
  also enforced by the boot guard.
- Grant vault access only to the people and API keys that genuinely need to recover
  original values; review `GET /api/v1/vault/grants` periodically.
- Terminate TLS in front of the deployment (an ALB on AWS, a reverse proxy locally);
  PIIShield's own app layer adds no transport encryption of its own.
- Do not set `KEY_MODE=kms` against this release's application image; see
  [docs/guides/deploy-aws.md](docs/guides/deploy-aws.md) for the real gap between the
  Terraform (which already sets it for `aws-dev`/`aws-prod`) and the 0.1.0 app code (which
  does not implement it).
