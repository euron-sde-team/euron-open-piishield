# Low-level design

This document walks the code: how the API is laid out, what each domain package owns, and
the exact algorithms behind detection, protection, tokenization and the AI gateway's trust
boundary. The system view is in [HLD.md](HLD.md); the schema is in
[data-model.md](data-model.md). Paths are relative to `apps/api/src/piishield/` unless
they start with `apps/`, `infra/` or `deploy/`.

- [Repository layout](#repository-layout)
- [Layering](#layering)
- [core](#core)
- [Domain packages](#domain-packages)
- [Detection: scan_text and overlap resolution](#detection-scan_text-and-overlap-resolution)
- [Checksums](#checksums)
- [Protection and the policy snapshot](#protection-and-the-policy-snapshot)
- [The vault: tokenize, resolve_in_scope, detokenize](#the-vault-tokenize-resolve_in_scope-detokenize)
- [Envelope encryption: the Sealer protocol](#envelope-encryption-the-sealer-protocol)
- [The AI gateway: protect and restore](#the-ai-gateway-protect-and-restore)
- [Documents: dispatch and per-leaf reuse](#documents-dispatch-and-per-leaf-reuse)
- [Auth: sessions, API keys, vault access](#auth-sessions-api-keys-vault-access)
- [The audit log](#the-audit-log)

## Repository layout

```
apps/api/                 FastAPI service, CLI and the mock AI upstream
  src/piishield/           the product
  src/mockai/               deterministic mock upstream (demo and tests)
  tests/unit/               no network, no database
  tests/integration/        real Postgres, Redis and the mock AI over HTTP
apps/web/                 Next.js 15 dashboard
sdks/python/, sdks/node/  SDKs, both typed around the five-category wire format
deploy/compose/           compose.yaml + compose.floci.yaml (+ compose.aws.yaml)
infra/terraform/          modules/ + envs/{local-floci,aws-dev,aws-prod}
scripts/                  gen-local-env.sh, test-matrix.sh, check-sanitization.sh
docs/                     PLAN.md, architecture/, guides/, api/openapi.yaml
```

## Layering

Packaged by domain. Within a domain, dependencies point inward:

```
router.py        HTTP only: parse, authorize (a dependency from auth/dependencies.py),
                  call the service, shape the response. No SQL, no detection logic.
schemas.py        Pydantic request/response models: the public contract.
service.py         business rules; the only place a domain's invariants live.
repository.py        the only code that queries the DB for this domain.
models.py           SQLAlchemy models owned by this domain.
```

A domain may call another domain's service, never its repository or models directly. The
one documented exception is `vault.service.resolve_in_scope`, an internal cross-domain
entrypoint `ai_gateway.service.restore` calls directly because `restore` is a different
trust boundary from the human-facing `vault.service.detokenize` (see
[below](#the-ai-gateway-protect-and-restore)); `protection.service` similarly calls
`vault.service.tokenize` for any category protected by tokenization. No other domain
service ever imports `Sealer.open` or reaches into another domain's models.

## core

| Module | Responsibility |
| --- | --- |
| [`core/config.py`](../../apps/api/src/piishield/core/config.py) | `Settings` (pydantic-settings) and `guard()`, the production boot guard. `get_settings()` is cached and calls the guard. |
| [`core/db.py`](../../apps/api/src/piishield/core/db.py) | Async engine, session factory, `Base`, the `OrgScoped` mixin and `OrgScope` the repositories require. |
| [`core/kv.py`](../../apps/api/src/piishield/core/kv.py) | `KV` protocol: `RedisKV` or `MemoryKV`. A KV outage degrades the policy cache and the tokenize scope map to a slower, still-correct path; it never blocks a scan or protect call (see [HLD.md](HLD.md)'s caching table). |
| [`core/sealing.py`](../../apps/api/src/piishield/core/sealing.py) | `Sealer` protocol, `LocalSealer`, `build_sealer`. See [below](#envelope-encryption-the-sealer-protocol). |
| [`core/security.py`](../../apps/api/src/piishield/core/security.py) | API key generation/parsing (`parse_api_key`, `API_KEY_PREFIX`), peppered HMAC (`hash_key_secret`), `constant_time_equals`, session encode/decode (`decode_session`). |
| [`core/deps.py`](../../apps/api/src/piishield/core/deps.py) | `ContainerDep` (settings, kv, sealer), `SessionDep`. |
| [`core/errors.py`](../../apps/api/src/piishield/core/errors.py) | Typed exceptions and the handler that maps them to `{"error": {"code", "message", "details"}}`. |
| [`main.py`](../../apps/api/src/piishield/main.py) | `create_app()`: wires every domain router, error handlers, CORS, request middleware. |
| [`cli.py`](../../apps/api/src/piishield/cli.py) | `piishield serve \| migrate \| revision \| openapi \| create-admin \| seed-demo`. |

## Domain packages

| Package | Owns | Notable detail |
| --- | --- | --- |
| `auth` | API keys, session dependencies, role and vault-access gates | `dependencies.py`'s `staff(role)` and `vault_access` (see [below](#auth-sessions-api-keys-vault-access)) |
| `orgs` | Organizations, users, roles, `vault_access` boolean | `User.vault_access` is independent of `role` |
| `projects` | Projects, the scoping boundary for keys, policies, recognizers, vault entries | `ensure_project` is called by every other domain's write path that takes a `project_id`, so a dangling cross-org row can never be created (see `policies.service.upsert`'s own comment on this) |
| `detectors` | The recognizer table, checksums, `scan_text`, per-project custom recognizers | See [below](#detection-scan_text-and-overlap-resolution) |
| `protection` | Full mask, partial mask, redact, tokenize; `protect_text`, `protect_json` | Calls `vault.service.tokenize` for any category resolved to `tokenize`; never calls `Sealer.open` |
| `vault` | The encrypted mapping store, detokenization, vault access grants | The only domain whose service ever calls `Sealer.open` outside of `ai_gateway.service.restore`'s direct call to `resolve_in_scope` |
| `policies` | Per-project required categories, masking method per category, confidence threshold, retention; the policy snapshot cache | See [below](#protection-and-the-policy-snapshot) |
| `documents` | PDF/DOCX/XLSX/CSV dispatch and per-leaf reuse of `protection.service.protect_text` | See [below](#documents-dispatch-and-per-leaf-reuse) |
| `database_scan` | Read-only, column-level sampling against a caller-supplied connection string | The connection string is never persisted; only `table_name`, `rows_sampled` and the per-column findings are |
| `ai_gateway` | `protect` (always tokenizes) and `restore` (scope-bound placeholder resolution) | See [below](#the-ai-gateway-protect-and-restore) |
| `review` | The low-confidence queue: `queue_finding`, `list_pending`, `approve`, `dismiss` | A review item never stores `matched_text`, only category, span, confidence and recognizer |
| `audit` | The append-only log; the only writer is `audit.service.record` | See [below](#the-audit-log) |
| `health` | `/healthz`, `/readyz`, `/metrics` | |

## Detection: scan_text and overlap resolution

`detectors/recognizers.py` defines `RECOGNIZERS`, an ordered list of `Recognizer(name,
category, pattern, confidence, validate)`. `scan_text(text, recognizers=None, max_chars=
MAX_SCAN_CHARS)` walks the list **in order** and, for each regex match, calls
`rec.check(m)`:

```python
def check(self, m: Match[str]) -> tuple[bool, bool | None]:
    if self.validate is None:
        return True, None
    return self.validate(m)   # (ok, checksum_valid | None)
```

`ok=False` means "this match cannot be this category at all" (the checksum failed), and
the match is dropped entirely, not reported at a lower confidence. This is what makes a
random 16-digit string provably not a credit card: `_card_validate` runs `luhn_ok` on the
digits and returns `(False, None)` when it fails, so the match never becomes a `Finding`.

**Overlap resolution** is first-claim-wins by list order: `scan_text` keeps a `taken` list
of already-claimed `(start, end)` spans, and a later recognizer's match is skipped if it
overlaps any span already taken, regardless of that later recognizer's own confidence.
The table is ordered most-specific/highest-signal first (`jwt`, `api_key`,
`password_assignment`, `credit_card`, `iban`, `swift_bic`, `ifsc`, `email`, `upi_id`,
`aadhaar`, `pan`, `us_ssn`, `passport`, `driving_licence`, `phone_in`, `phone_us`, then the
unvalidated `bank_account` digit-count match, then `date_of_birth`, `address`,
`person_name`). `bank_account` is deliberately last among the digit-shaped recognizers: it
has no checksum (PLAN.md calls it "pattern-assisted" only), so every checksum- or
format-validated recognizer above it claims its span first; otherwise a valid Aadhaar, SSN
or phone number could be stolen by the generic digit-count match before the correct
recognizer ever saw it. See [ADR-0003](adr/0003-fixed-priority-overlap-resolution.md).

A per-project custom recognizer (`custom_recognizer(name, category, pattern, confidence)`)
is compiled once and appended to the active list for that project's scans; an invalid
pattern raises `re.error` at creation time, caught at the router boundary as a 422, never
a 500.

`Finding.as_dict()` deliberately excludes `matched_text` (marked `field(repr=False)` on
the dataclass and simply absent from the dict): every caller that builds an API response
from a `Finding` uses `as_dict()` or its own `_finding_out` shaping function, never the
dataclass fields directly, so the original value cannot leak into a response by a future
contributor forgetting to strip it.

## Checksums

`detectors/checksums.py` has one pure function per validated category:

- `luhn_ok(digits)`: mod-10 Luhn, cards and some bank ids.
- `verhoeff_ok(digits)`: the Verhoeff checksum (dihedral group D5 tables), the last digit
  of a 12-digit Aadhaar number.
- `iban_ok(raw)`: ISO 7064 MOD 97-10 exactly as specified for IBAN (move the first 4
  characters to the end, map each letter A-Z to 10-35, the resulting number mod 97 must
  equal 1).
- `pan_entity_ok(fourth_char)`: the 4th character of a PAN encodes an entity type (person,
  company, HUF, firm, AOP, trust, body of individuals, local authority, artificial
  judicial person, government); anything else cannot be a PAN.
- `us_ssn_ok(area, group, serial)`: SSA well-formedness rules (no `000`/`666`/`9xx` area,
  no `00` group, no `0000` serial); explicitly documented as not a true checksum, since SSNs
  have none.
- `ifsc_ok(code)`: structural check only (4 letters, a literal `0`, 6 alphanumeric), no
  public checksum digit exists for IFSC.

Every caller strips non-digit characters before calling the digit-based functions; the
functions themselves do no formatting work.

## Protection and the policy snapshot

`policies/service.py` is a read-through cache keyed by `project_id`:

```python
async def load(session, kv, scope, project_id, *, fresh=False) -> PolicySnapshot:
    version = await _current_version(kv, project_id)
    cached = _local_cache.get(project_id)
    if not fresh and cached is not None:
        cached_at, cached_version, snapshot = cached
        if cached_version == version and now - cached_at < 5.0:
            return snapshot
    row = await repository.get_for_project(session, scope, project_id)
    snapshot = _to_snapshot(row) if row is not None else _DEFAULT
    _local_cache[project_id] = (now, version, snapshot)
    return snapshot
```

A cache hit requires both the in-process entry to be younger than
`policy_cache_ttl_s` (default 5s) **and** its stored version to still match the version
stamp in KV. `upsert` bumps that stamp (`bump`) and clears this process's own entry
(`forget`) in the same call, after commit. A write on one replica is visible to every
other replica within the TTL even with no pub/sub channel, because every replica re-reads
the version stamp on every call, cheap enough to do unconditionally. See
[ADR-0002](adr/0002-bounded-staleness-policy-cache.md) for why this is a deliberate
staleness window rather than instant invalidation.

`protection.service.protect_text` / `protect_json` use the loaded `PolicySnapshot` to
decide, per finding: is the category required (`is_required`); what method applies
(`method_for`, falling back to `tokenize`); and whether confidence clears
`confidence_threshold`. A finding below threshold and not required is queued to
`review.service.queue_finding` and left unprotected in the output; a finding below
threshold but required is protected anyway and still queued for review (acceptance
criteria 10 and 13). `method_overrides` passed by a caller (or hardcoded by the AI gateway,
see below) takes precedence over the policy's own `masking_method` for that call.

## The vault: tokenize, resolve_in_scope, detokenize

`vault/service.py` enforces acceptance criterion 4 (scope-consistent tokenization, no
collisions) through a fingerprint, not the plaintext:

```python
_FINGERPRINT_CONTEXT = b"piishield-vault-fingerprint-v1"

def _fingerprint(value: str) -> str:
    return hmac.new(_FINGERPRINT_CONTEXT, value.encode(), hashlib.sha256).hexdigest()
```

`tokenize(session, kv, sealer, actor, project_id, scope_id, category, value)`:

1. Compute `fp = _fingerprint(value)`. Check the KV cache
   (`piishield:tokenize:<org>:<project>:<scope_id>:<fp>`) for a placeholder; if present,
   confirm the vault row still exists (`find_by_placeholder`) before trusting it, so a
   stale or dangling cache entry falls through rather than being trusted blindly.
2. On a cache miss, look up the durable row by fingerprint
   (`find_by_fingerprint`, unique on `(org_id, scope_id, placeholder)` is enforced at the
   table level, the fingerprint lookup is a separate indexed column). If found, warm the
   cache and return its placeholder.
3. Otherwise this is a new value in this scope: count existing placeholders for this
   `(project, scope_id, category)` to compute the ordinal, build `[CATEGORY_NNN]`, seal
   the plaintext (`sealer.seal(value, vault_context(entry_id))`), insert the row, warm the
   cache, return the placeholder.

Because the durable table, not the cache, is the source of truth (step 2 always runs on a
cache miss, and a KV outage simply means every call takes that path), scope consistency
never depends on Redis being up or warm.

`resolve_in_scope(session, sealer, scope, project_id, scope_id, placeholder)` is the
internal function both `detokenize` (below) and `ai_gateway.service.restore` call: it
looks up the vault row for that exact `(scope, project_id, scope_id, placeholder)` and, if
found, opens it (`sealer.open(Sealed.decode(entry.sealed_value), vault_context(entry.id))`)
and returns `(value, category)`, or `None` if nothing matches.

`detokenize(session, sealer, actor, project_id, scope_id, placeholder)` is the **only
human-facing** function that decrypts a vault row; it calls `resolve_in_scope` and raises
`PlaceholderNotFoundError` on a miss. It performs no permission check of its own: the
`VaultAccess` FastAPI dependency at the router boundary (`vault/router.py`'s
`POST /vault/detokenize`) is the only place that decision is made, so there is exactly one
place in the codebase deciding who may call this.

## Envelope encryption: the Sealer protocol

```python
class Sealer(Protocol):
    async def seal(self, plaintext: str, context: str) -> Sealed: ...
    async def open(self, sealed: Sealed, context: str) -> str: ...
```

`LocalSealer` derives a 32-byte AES key from `hashlib.sha256(master_key.encode())`, so
`LOCAL_MASTER_KEY` can be any length or encoding. `seal` generates a fresh 12-byte nonce
per call, encrypts with `AESGCM(key).encrypt(nonce, plaintext, context.encode())`, and
stores `nonce + ciphertext` as the `Sealed` blob. `context` is AEAD associated data, not
part of the ciphertext bytes themselves, but required, byte-identical, to open it again:
`vault.service.vault_context(entry_id)` returns `f"vault:{entry_id}"`, so a `sealed_value`
copied from one vault row into another fails to decrypt (`SealError`).

`build_sealer(key_mode, local_master_key, kms_key_id)` is the one factory every container
calls at startup. For `key_mode == "kms"` it raises `NotImplementedError` immediately: a
deployment that asks for KMS and does not get it must fail loudly at boot, not silently
fall back to a weaker backend. Only `key_mode == "local"` returns a working `Sealer` in
0.1.0. See [ADR-0001](adr/0001-envelope-encryption-local-key-only.md).

## The AI gateway: protect and restore

`ai_gateway/service.py protect` always resolves every category to `tokenize`, regardless
of the project's own policy `masking_method`:

```python
method_overrides={
    "financial": "tokenize", "government_id": "tokenize", "contact": "tokenize",
    "personal": "tokenize", "credential": "tokenize",
}
```

This is deliberate, not a bug: the gateway's whole purpose is restoring the exact original
value into the calling application's copy of the model's response, which only
tokenization (not masking or redaction) makes possible. A finding that lands below the
confidence threshold still goes to the review queue and is left unprotected in the
outgoing prompt, the same behavior as any other protect call.

`restore(session, sealer, scope, actor, project_id, scope_id, model_response)` finds every
`[CATEGORY_NNN]`-shaped substring (`_PLACEHOLDER = re.compile(r"\[[A-Z_]+_\d{3}\]")`) in
the model's response and calls `vault.service.resolve_in_scope` directly (not
`vault.service.detokenize`) for each one, scoped to the exact `(org, project, scope_id)`
the caller supplies. A placeholder that does not resolve in that scope, including a
bracketed string the model generated on its own that merely looks like a placeholder, is
left untouched rather than erroring.

This is a different trust boundary from the human `detokenize` call, and the module
docstring says so explicitly: `restore` is **not** gated by the `VaultAccess` permission.
The reasoning is that `restore` completes a round trip the caller itself started with its
own earlier `protect` call: the caller already received `scope_id` once, in the `protect`
response, and `scope_id` is never embedded in the protected prompt sent to the model (so
the model, and anyone who only sees the model's traffic, never learns it). A caller who
does not already possess a valid `scope_id` cannot discover one by guessing: a wrong
`scope_id` simply resolves nothing, by construction of the lookup being scoped on it. See
[security.md](security.md) and [threat-model.md](threat-model.md) for the full reasoning,
and [ADR-0002](adr/0002-bounded-staleness-policy-cache.md)/
[ADR-0003](adr/0003-fixed-priority-overlap-resolution.md) for the program's other recorded
decisions in this area.

## Documents: dispatch and per-leaf reuse

`documents/service.py protect_document(session, kv, sealer, actor, project_id, filename,
data, scope_id=None)` dispatches on file extension (`pdf`, `docx`, `xlsx`, `csv`) to a
per-format processor (`documents.pdf.protect_pdf`, `documents.docx_.protect_docx`,
`documents.xlsx_csv.protect_xlsx` / `protect_csv`). Every processor is handed the same
closure, `_protect_leaf(text) -> (protected_text, findings)`, which simply calls
`protection.service.protect_text` for that one page, paragraph or cell, scoped to a single
`resolved_scope` (generated once per document call) so tokenized values are consistent
across the whole document. Reusing `protect_text` means documents get exactly the same
detection, policy, confidence-threshold and tokenization behavior as text and JSON, rather
than a second implementation of any of it.

Because `protect_text` commits and records its own `scan_events`/audit row per leaf, a
large spreadsheet produces one scan/audit entry per cell scanned; `protect_document` itself
then also writes one `document_scans` row (aggregated finding count, categories, and a
per-page/sheet `breakdown`) and one audit entry for the call as a whole. 0.1.0 accepts the
per-leaf duplication as the cost of correctness-first reuse rather than a second,
divergent code path; it is documented here rather than left as a silent surprise.

Document bytes themselves are never persisted: `protect_document` returns
`(protected_file_bytes, file_type)` directly in the HTTP response body (not a JSON findings
report, see `documents/router.py`), so an upload of a 10-page PDF comes back as a protected
PDF, not a text dump.

## Auth: sessions, API keys, vault access

`auth/dependencies.py` resolves a caller from either a dashboard session (`Authorization:
Bearer <session token>`, decoded by `decode_session`) or a project API key
(`pii_<prefix>_<secret>`, looked up by `prefix`, verified with
`constant_time_equals(key.secret_hash, hash_key_secret(secret, pepper))`). A read-scoped
key acts like `viewer`; a write-scoped key acts like `admin`
(`role = "admin" if key.scope == "write" else "viewer"`); `staff(role)` compares against
`ROLE_RANK = {"viewer": 0, "admin": 1, "owner": 2}`.

Vault access is resolved separately and cached per-request on `request.state.vault_access`:
for a user, it is the `vault_access` boolean column on `orgs.models.User`; for an API key,
it is whether an active `VaultGrant` row exists for that key id
(`VaultGrant.api_key_id == key.id, revoked_at IS NULL`). The `vault_access` dependency
raises `PermissionDeniedError(code="vault_access_required")` when neither is true,
regardless of the caller's role or key scope. See [security.md](security.md).

## The audit log

`audit/service.record(session, actor, action, *, project_id=None, finding_count=0,
categories=None, **details)` has no parameter through which a raw matched value could ever
be passed: every call site passes `finding_count` (an int) and `categories` (a list of the
five coarse category strings), never `matched_text`. `details` additionally passes through
`_sanitize_details`, which recursively drops any key named `value`, `original_value`,
`plaintext`, `raw`, `text`, `content`, `password`, `secret`, `secret_hash`, `token`,
`api_key` or `ciphertext` from whatever a caller passes. This makes acceptance criterion 11
(the audit log never contains an original value) true by construction rather than by
review: there is no code path from a detector's match, or from a vault's plaintext, back
into an audit row.

A per-organization sequence number (`seq`) is assigned by a scalar subquery
(`MAX(seq) + 1 WHERE org_id = ...`) so concurrent writers from the same org still produce
a consistent total order without a separate counter table.

`list_entries` caps `limit` at 200 (`min(limit, 200)`) regardless of what a caller asks
for, and `audit/router.py`'s `AuditPage.next_cursor` is always `None` in 0.1.0: there is no
real cursor-based pagination yet, only the hard cap. See [security.md](security.md) for
this stated as a known 0.1.0 limitation.
