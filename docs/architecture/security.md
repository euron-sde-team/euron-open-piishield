# Security

PIIShield holds two kinds of sensitive material: the original values it detects (while a
request is in flight) and, when tokenization is the chosen protection method, the
encrypted mapping that lets an authorized caller get an original value back later. This
document covers how both are protected, who can do what, and what an operator must
configure. The threat analysis is in [threat-model.md](threat-model.md).

## Envelope encryption (the vault)

Every tokenized value's plaintext is encrypted with a fresh, random 256-bit AES-GCM key
(the "envelope" is the pattern: each row gets its own data key, wrapped by a longer-lived
master key; see `core/sealing.py`). Concretely:

- `Sealer.seal(plaintext, context)` generates a 12-byte random nonce and encrypts with
  `AESGCM(key).encrypt(nonce, plaintext, context.encode())`; the stored blob is
  `nonce + ciphertext`.
- `context` is bound as AEAD associated data, not stored as part of the ciphertext: a
  sealed blob only opens again under the exact context it was sealed with. Every vault
  entry's context is `vault:<entry_id>` (`vault.service.vault_context`), so a
  `sealed_value` copied from one row to another (a bug, a backup restored into the wrong
  row, an attacker splicing rows) fails to decrypt instead of silently opening.
- 0.1.0 ships exactly one key backend, `key_mode=local`: the AES key is
  `sha256(LOCAL_MASTER_KEY)`. `build_sealer` raises `NotImplementedError` immediately for
  `key_mode=kms`, on purpose: a deployment that asks for KMS and does not get a working
  KMS-backed sealer must fail loudly at boot, never silently fall back to a weaker
  backend. **This is a real, deliberate scope limit for 0.1.0, not a bug.** A future
  KMS-backed `Sealer` implementing the same `Protocol` (`seal`/`open`) is the roadmap; see
  [ADR-0001](adr/0001-envelope-encryption-local-key-only.md).
- A leaked database alone, without `LOCAL_MASTER_KEY`, never recovers a tokenized value:
  every `vault_entries.sealed_value` is ciphertext, and the master key lives only in the
  deployment's environment/secret store.

## The vault-access permission

Detokenization (`POST /api/v1/vault/detokenize`) requires a permission that is **separate
from role and from API key scope**, never implied by `owner`, `admin`, or a write-scoped
key alone (acceptance criterion 5):

- For a dashboard user, it is the `vault_access` boolean column on `orgs.models.User`,
  set independently of `role`.
- For an API key, it is whether an active `VaultGrant` row exists for that key
  (`vault_grants.api_key_id`, `revoked_at IS NULL`).
- Granting or revoking vault access (`POST`/`GET`/`DELETE /api/v1/vault/grants`) is itself
  restricted to the `owner` role: deciding who can decrypt is treated as sensitive as
  decrypting.
- The check happens in exactly one place, the `VaultAccess` FastAPI dependency
  (`auth/dependencies.py`); `vault.service.detokenize` performs no permission check of its
  own, so there is no second code path that could get this wrong.
- A caller without vault access gets a 403 with a message that explains what is missing
  (`"This action needs vault access, which is granted separately from your role"`), never
  the value and never a hint that the placeholder resolved to something (acceptance
  criterion 5).

**The AI gateway's `restore` is not the same operation and is not gated by
`VaultAccess`.** It resolves placeholders for the application that itself just called
`protect` and received a `scope_id`, as the second half of one round trip, not a new act
of reaching into someone else's vault. See [threat-model.md](threat-model.md) for the full
reasoning behind why this is safe without the same gate.

## API key authentication

- Format `pii_<prefix>_<secret>`, parsed by `core/security.py parse_api_key`.
- Looked up by `prefix` (12 hex characters, indexed, unique), then verified by
  `constant_time_equals(key.secret_hash, hash_key_secret(secret, API_KEY_PEPPER))`. The
  secret itself is never stored, only its peppered HMAC; a leaked database alone cannot be
  turned into a working key without the pepper.
- `scope` is `read` or `write`. A read key authorizes like `viewer`; a write key
  authorizes like `admin`. **Neither scope ever implies vault access**, which is always a
  separate `VaultGrant`.
- Revoked keys (`revoked_at` set) are rejected the same way an invalid key is: no
  distinction is leaked in the error.

## Dashboard sessions

- Sessions are decoded by `core/security.py decode_session` against `SESSION_SECRET`.
- Every session carries the user's `session_version`; changing a password bumps it,
  which invalidates every existing session for that user immediately on their next
  request, without needing a server-side revocation list for the common case.
- A disabled user (`disabled=true`) is rejected even with an otherwise valid, unexpired
  session.

## Tenant isolation

Every table except `organizations` carries `org_id`. Every repository function that reads
or writes a row takes an `OrgScope` built from the caller's own `org_id`, never a bare id
passed around separately; there is no route that can "forget" to scope a query, because
the repository functions require the scope argument to run at all. A lookup for another
organization's project, policy, vault entry, custom recognizer, scan record or audit row
returns **404, never 403**, and never a hint that the row exists at all for someone else
(acceptance criterion 12). `policies.service.upsert` additionally calls `ensure_project`
before any write, specifically because a naive "insert if missing" would otherwise create
a dangling policy row keyed to a `project_id` the caller's org does not own, the moment a
caller supplies another org's project id to a PUT.

## The audit log's no-raw-value guarantee

`audit.service.record(session, actor, action, *, project_id=None, finding_count=0,
categories=None, **details)` has no parameter through which a raw matched value, a vault
plaintext, or a prompt/response body could be passed; every call site passes counts
(`finding_count`) and coarse category labels (`categories`), never `matched_text`.
`details` additionally passes through `_sanitize_details`, which recursively drops any key
named `value`, `original_value`, `plaintext`, `raw`, `text`, `content`, `password`,
`secret`, `secret_hash`, `token`, `api_key` or `ciphertext`. This makes acceptance
criterion 11 (the audit log never contains an original value) true by construction, not by
code review discipline: there is no code path from a detector's match or a vault's
plaintext back into an audit row. The same property holds for `scan_events`,
`review_items`, `document_scans` and `database_scan_results`, see
[data-model.md](data-model.md)'s "what is deliberately never stored" section.

**Known 0.1.0 limitation:** `audit.service.list_entries` caps `limit` at 200
(`min(limit, 200)`), and the API's `AuditPage.next_cursor` is always `null`; there is no
cursor-based pagination beyond that hard cap yet. An organization with more than 200
matching entries sees only the most recent 200. This is a real gap to fix, not a security
hole (no data is lost, only unreachable through this endpoint past the cap), and it is
stated here plainly rather than left for someone to discover.

## Production boot guards

`core/config.py Settings.guard()` runs once at startup and refuses to boot in
`environment=production` with unsafe defaults:

- `API_KEY_PEPPER` and `SESSION_SECRET` must each be at least 32 characters and not one of
  the known insecure defaults (`""`, `"change-me"`, `"dev"`, `"secret"`,
  `"replace-with-output-of-make-env"`, or containing `"not-for-production"`).
- With `key_mode=local`, `LOCAL_MASTER_KEY` is held to the same standard. (`key_mode=kms`
  is not a way around this guard: it is not implemented at all in 0.1.0, see above.)
- `CORS_ORIGINS` must not contain `"*"`.
- `COOKIE_SECURE` must be `true`.

Any violation raises `RuntimeError("unsafe production configuration: ...")` listing every
problem found, so a misconfigured production deployment fails at boot rather than serving
traffic insecurely.

## Config fields accepted but not yet backed by real behavior

Two settings exist in `core/config.py` for parity with the deployment's env contract, but
0.1.0's app code has no branch that uses them yet:

- `storage` (`local`/`s3`): document protection is request-scoped in 0.1.0 (the protected
  file is returned directly in the HTTP response, never written to disk or to S3, see
  `documents/service.py`), so this field is accepted at boot but currently has no effect.
- `aws_secrets_enabled`: there is no Secrets Manager read path in 0.1.0's app code; secrets
  are read from the environment the same way regardless of this flag.

Both exist so the container boots cleanly against the deployment's full env contract
without erroring on an unrecognized variable, and so a future implementation has an
established name to read from. Neither is a security control today; nothing should be
assumed enabled because this setting is present. See
`deploy/compose/compose.floci.yaml`'s own comment on this for the matching Floci-side
notes (the KMS key/alias Terraform provisions on Floci exists for `tf-aws-on-floci` and a
future KMS sealer to target, but nothing in 0.1.0's app code reads it yet).

## HTTP hardening

- Every input is validated at the boundary through Pydantic request schemas; a malformed
  custom recognizer pattern is rejected as a 422 at creation, never stored broken.
- Errors never leak stack traces; the error handler maps every typed exception to
  `{"error": {"code", "message", "details"}}`.
- `max_body_bytes` and `max_scan_chars` (both configurable) bound request size and the
  amount of text a single scan will process.

## Data handling

- Prompts, document bytes and scanned-column samples are never persisted beyond the
  request that submits them (see [data-model.md](data-model.md)'s full list of what is
  never stored).
- A database scan's connection string and credentials are supplied per call and never
  written to any table.
