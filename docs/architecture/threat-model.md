# Threat model

Scope: the API, Postgres, Redis, the AWS resources the Terraform creates, and the
dashboard. Method: STRIDE per asset, with the mitigation that exists in this
repository today and the residual risk.

## Assets

1. **Original PII and financial values** passed into a scan, protect, document or AI
   gateway call, for the duration of the request.
2. **Tokenized values held in the vault** (the only durable form an original value can
   take, and only when the protection method chosen is `tokenize`).
3. **The vault master key** (`LOCAL_MASTER_KEY` in 0.1.0).
4. **API keys and dashboard sessions.**
5. **Tenant isolation** (one organization never sees another's projects, policies, vault
   entries, reports or audit records).
6. **The audit log's integrity and its no-raw-value guarantee.**
7. **Prompts and model responses in transit through the AI gateway.**

## Threats and mitigations

| # | Threat (STRIDE) | Asset | Mitigation | Residual risk |
| --- | --- | --- | --- | --- |
| T1 | Information disclosure: a leaked database recovers tokenized values | 2, 3 | Envelope encryption (AES-256-GCM, per-record data key derived from the master key, AEAD context bound to the vault entry's own id); the master key is never stored alongside the data | A leaked `LOCAL_MASTER_KEY` together with the database recovers every vault entry; see T6 |
| T2 | Tampering: a ciphertext is copied from one vault row to another to forge a value | 2 | AEAD associated data is `vault:<entry_id>`; a sealed blob only opens under the exact context it was sealed with, so a copied ciphertext fails to decrypt (`SealError`) | None known |
| T3 | Elevation: a write-scoped API key or an admin/owner role reads the vault without being granted vault access | 2 | `VaultAccess` is a dependency checked independently of role and of key scope, backed by a separate `VaultGrant` row; `vault.service.detokenize` performs no check of its own, there is exactly one place this is decided | A compromised `owner` account can grant itself vault access through `POST /vault/grants`; that action is itself audited |
| T4 | Spoofing: a guessed or brute-forced `scope_id` is used to call the AI gateway's `restore` and pull values from a scope the caller never created | 2, 7 | `scope_id` is an opaque, unguessable token only ever returned once, to the caller that made the matching `protect` call, and never embedded in the prompt sent to the model; a wrong `scope_id` resolves no placeholders, by construction of the lookup | A `scope_id` leaked through the calling application's own logs or network traces could be replayed against `restore`; that is the calling application's responsibility, not PIIShield's, since PIIShield never logs it either |
| T5 | Information disclosure: the audit log or scan/review records leak an original value | 1, 6 | `audit.service.record` has no raw-value parameter and `_sanitize_details` drops value-like keys; `scan_events`, `review_items`, `document_scans` and `database_scan_results` store only counts, categories, spans and confidence, never matched text | None known within the documented code paths; a future contributor adding a new audit call site that passes a raw value through an unrecognized `details` key name would not be caught automatically unless that key matches `_VALUE_LIKE_KEYS` |
| T6 | Information disclosure: a compromised API host's environment variables expose `LOCAL_MASTER_KEY`, `API_KEY_PEPPER` or `SESSION_SECRET` | 3, 4 | Secrets are read from the environment only, never logged, never returned in any response; production boot guards (`Settings.guard()`) refuse known-insecure defaults | Compromise of the host itself is out of scope (see [SECURITY.md](../../SECURITY.md)); 0.1.0 has no KMS-backed key isolation yet (see T9) |
| T7 | Spoofing: a stolen API key is used from elsewhere | 4 | Keys are peppered HMACs, not reversible; `prefix` lookup plus constant-time comparison; revocation is immediate (`revoked_at`) | A stolen key works until revoked; there is no built-in per-key rate limit in 0.1.0 |
| T8 | Elevation: cross-tenant access to another organization's data | 5 | Every repository query is structurally scoped by `OrgScope`; a cross-org lookup returns 404, never 403, never a hint of existence (acceptance criterion 12) | None known; this depends on every new repository function continuing to require an `OrgScope` argument, which the layering makes hard to skip |
| T9 | Information disclosure / tampering: `key_mode=kms` is requested but not available | 3 | `build_sealer` raises `NotImplementedError` at boot for `key_mode=kms`, refusing to silently fall back to a weaker backend | 0.1.0 genuinely has no KMS-backed sealer; an operator who needs hardware-backed key isolation cannot get it from this release (documented scope limit, [ADR-0001](adr/0001-envelope-encryption-local-key-only.md)) |
| T10 | Detection evasion: a value is formatted or presented in a way no 0.1.0 recognizer covers | 1 | Checksum validators eliminate false positives (a value that fails Luhn/Verhoeff/mod-97/the PAN entity rule is never reported as that category at all); per-project custom recognizers let an operator add a pattern | 0.1.0 has no OCR (an image or a scanned PDF's rendered text is invisible to every recognizer) and no full NER (a name or address outside the pattern/dictionary-assisted recognizers can be missed); this is a real, known detection gap, not a bug, and is the first item on the roadmap |
| T11 | Denial of service: a KV (Redis) outage disables the policy cache or tokenization scope map | 1, 2 | Both are designed to degrade, never fail closed: the policy service falls back to a direct database read, and tokenization falls back to the durable vault table lookup for scope consistency (`core/kv.py`'s own docstring: "a privacy/detection tool degrades predictably, never fails closed") | Slower responses during the outage; no loss of correctness |
| T12 | Tampering: a policy change (e.g. disabling masking for a required category) does not take effect immediately on every replica | all protected content | The policy cache's bounded 5-second staleness window is a deliberate, documented tradeoff (see [ADR-0002](adr/0002-bounded-staleness-policy-cache.md)) | A protect call on another replica within the TTL window can use the stale policy; acceptable for a confidence threshold or masking-method setting, unacceptable if this product ever needs instant kill-switch semantics, which it does not claim to provide in 0.1.0 |
| T13 | Repudiation: no record of who detokenized a value or changed a policy | 6 | Every mutation (`detokenize`, `policy.updated`, `review.approved`/`dismissed`, vault grant create/revoke) writes an audit row in the same transaction as the change | Audit rows are readable by any `viewer`-or-above role or a read-scoped key; there is no further restriction on who can read the audit log itself in 0.1.0 |
| T14 | Information disclosure: findings-in-transit over an unencrypted channel | 1, 7 | TLS termination is the deployment's responsibility (ALB on AWS, a reverse proxy locally); PIIShield's own app layer adds no additional transport encryption | A deployment that skips TLS exposes everything in transit; documented as an operator responsibility, consistent with the program's other projects |

## Out of scope for 0.1.0

- A compromised host or AWS account, or a leaked deployment secret file: see
  [SECURITY.md](../../SECURITY.md).
- Image OCR, scanned-PDF redaction, and full NER-based name/address detection (PLAN.md's
  roadmap, deferred to avoid an OCR/NER dependency this program avoids pulling in by
  default for 0.1.0).
- Database write-back anonymization: the 0.1.0 database scan is read-only and advisory; it
  never modifies the scanned database, so there is no risk of PIIShield itself corrupting
  or mis-anonymizing a live table, but also no protection from this feature until that
  roadmap item ships with its own safety review.
- KMS-backed key sealing (`key_mode=kms`): explicitly not implemented, see T9.
- Audit log pagination past the 200-row cap: a usability and completeness gap, not a
  confidentiality one (see [security.md](security.md)).
