# euron-piishield (Python)

The Python SDK for [Euron Open PIIShield](../../README.md), a self-hosted platform that
detects, masks, redacts, tokenizes and anonymizes personally identifiable and financial
information across text, JSON, documents, databases, and AI agent prompts and responses.
It is part of the open-source initiative of **ENGAGESPHERE TECHNOLOGY PRIVATE LIMITED**
and is MIT licensed.

This README is the canonical reference for the Python SDK: every method's signature,
every exception, the wire format it assumes, and the safety properties around
tokenization and the AI gateway. If you are writing documentation or a dashboard against
this SDK, read this file rather than the source.

```bash
pip install euron-piishield
```

The package is not on PyPI yet (publishing is on the roadmap). Until then install it from
this repository:

```bash
pip install ./sdks/python
# or, for local development against the source tree:
uv pip install -e ./sdks/python
```

## Quickstart

```python
from euron_piishield import PIIShield

shield = PIIShield(
    api_url="http://localhost:8000", api_key="YOUR_API_KEY", project_id="YOUR_PROJECT_ID"
)

text = "Customer: Rahul Sharma\nEmail: rahul@example.com\nPhone: 9876543210"
result = shield.mask(text)
print(result.protected_text)
```

```python
# AI gateway: protect a prompt before it reaches an external model.
protected = shield.protect("My PAN is ABCDE1234F. Explain my tax record.")
# Send only protected.protected_text to the external AI provider.
# protected.scope_id stays with you: see "AI gateway safety property" below.
```

For asyncio applications, `AsyncPIIShield` exposes the identical method set, awaited:

```python
from euron_piishield import AsyncPIIShield

async def main() -> None:
    async with AsyncPIIShield(
        api_url="http://localhost:8000", api_key="YOUR_API_KEY", project_id="YOUR_PROJECT_ID"
    ) as shield:
        result = await shield.mask("Email: rahul@example.com")
        print(result.protected_text)
```

Every example in this README that uses `PIIShield` works the same way on
`AsyncPIIShield` with `await` in front of the call; this document does not repeat each
example twice.

## Why sync is the primary client

The product brief's own example usage (`shield.mask(text)`, no `await`) is synchronous,
and most callers of this SDK are not already inside an asyncio event loop (CLI scripts,
Django views, simple Flask apps, notebooks). `PIIShield` is therefore the primary,
blocking client. `AsyncPIIShield` is provided as a first-class equal, not an afterthought,
because the rest of this program is async-first (FastAPI, SQLAlchemy async): use it in
any asyncio application (FastAPI route handlers, async workers) so a call to PIIShield
never blocks the event loop.

## Installation requirements

Python 3.10 or newer. The only runtime dependency is `httpx`.

## Client construction

```python
PIIShield(
    api_url: str,
    api_key: str,
    project_id: str,
    *,
    timeout: float = 30.0,
    http_client: httpx.Client | None = None,
)
```

`AsyncPIIShield` takes the same arguments, with `http_client: httpx.AsyncClient | None`.

- `api_url`: the PIIShield API's base URL, for example `http://localhost:8000` (or
  `http://localhost:5530` against this project's own local Compose stack; see
  `docs/PLAN.md`'s Ports section).
- `api_key`: a project API key (`pii_<prefix>_<secret>`), created under
  `POST /api/v1/auth/keys` with `scope: "write"` for every call in this README except the
  read-only ones (`get_policy`, `get_audit_logs`, `get_review_items`), which also accept a
  `scope: "read"` key.
- `project_id`: the project this client acts on behalf of. Every call is scoped to it:
  the server's structural tenant isolation means an API key from one project can never
  read or act on another project's data, policy, vault entries or audit log (AC12 of
  `docs/PLAN.md`).
- `timeout`: per-request timeout in seconds.
- `http_client`: supply your own `httpx.Client`/`httpx.AsyncClient` (for connection
  pooling shared with other code, custom proxies, or test instrumentation). The SDK
  closes it on `close()`/`aclose()` only when it created it itself.

Both clients are context managers (`with PIIShield(...) as shield:` /
`async with AsyncPIIShield(...) as shield:`) and both are safe to share across threads
(`PIIShield`) or asyncio tasks of one event loop (`AsyncPIIShield`).

## Method reference

### Detection: `scan`, `scan_json`

```python
shield.scan(text: str) -> ScanResult
shield.scan_json(payload: Any) -> ScanResult
```

`scan` calls the dedicated `POST /api/v1/detectors/scan` route: detection only, no
protection applied, no policy enforcement, and no audit entry written. Its findings have
no `method`/`placeholder`/`in_review` (the route does not protect anything, so those are
always `""`/`None`/`False`), and `review_count` is always `0`. `scan_json` has no
dedicated route of its own: it calls `protect/json` with every known category listed in
`skip_categories`, so nothing is actually masked, only detected, unless the project's
policy marks a category as required (then AC10 forces protection on that category
regardless of `skip_categories`, and that finding's `method` will not be `"skip"`). See
"Wire format" below.

`ScanResult`:

| Field | Type | Meaning |
| --- | --- | --- |
| `findings` | `list[Finding]` | every detected value (never the value itself) |
| `review_count` | `int` | how many of the findings were low-confidence and routed to the review queue instead of acted on |
| `raw` | `dict` | the unparsed response body |

`Finding` (matches `protection.schemas.ProtectedFindingOut` exactly):

| Field | Type | Meaning |
| --- | --- | --- |
| `category` | `str` | one of the five coarse categories every recognizer rolls up to: `"contact"`, `"credential"`, `"financial"`, `"government_id"`, `"personal"` (confirmed live against `piishield.detectors.recognizers.RECOGNIZERS`; use these exact strings in `method_overrides`/`skip_categories`, see `ALL_CATEGORIES`) |
| `start`, `end` | `int` | the exact character offsets of the match in the original text |
| `confidence` | `float` | 0.0 to 1.0 |
| `checksum_valid` | `bool \| None` | `True`/`False` where a checksum applies (Luhn for cards, Verhoeff for Aadhaar, ISO 7064 mod 97 for IBAN); `None` where no checksum applies to the category |
| `recognizer` | `str` | which specific detector matched, finer-grained than `category` (e.g. `"credit_card"`, `"pan"`, `"aadhaar"`, `"email"`, `"phone_in"`) |
| `method` | `str` | the protection method actually applied to this finding: `"full_mask"`, `"partial_mask"`, `"redact"`, `"tokenize"`, `"skip"` (left unmasked, from `scan`) or `"review"` (below the confidence threshold, not required) |
| `placeholder` | `str \| None` | the tokenize placeholder (e.g. `"[EMAIL_001]"`), set only when `method == "tokenize"` |
| `in_review` | `bool` | `True` when this finding was also routed to the review queue |

A `Finding` never carries the original matched value: PIIShield's own server-side
contract (AC6, AC11) is that the original value is returned only by an authorized
`detokenize` call, never by a protect, document or AI-gateway response, and never written
to the audit log. This SDK's model classes simply have no field that could hold it.

### Protection: one flexible call, plus brief-exact wrappers

This SDK ships **both** designs the brief suggested, kept internally consistent:

- **`mask(text, method=..., categories=...)`** is the one flexible call, matching the
  brief's `shield.mask(text)` example exactly. `method` selects which of the four
  protection methods to apply as an **override** for the named `categories` (or every
  detected category, if `categories` is omitted); it defaults to `"full_mask"`.
- **`redact(text)`**, **`anonymize(text)`** and **`tokenize(text, scope_id=...)`** are
  thin wrappers, each exactly equivalent to a specific `mask(...)` call. The real API has
  only one protect endpoint per content type (`protect/text`, `protect/json`): there is
  no separate `/redact` or `/anonymize` route, so these three wrappers all call the same
  `mask()` under the hood with a different `method`.
  - `redact(text, categories)` == `mask(text, method="redact", categories=categories)`
  - `anonymize(text, categories)` == `mask(text, method="full_mask", categories=categories)`
  - `tokenize(text, scope_id, categories)` == `mask(text, method="tokenize", scope_id=scope_id, categories=categories)`

Use whichever reads better at the call site; they are not two different behaviors, only
convenience names for the same underlying call. If you are building the web dashboard
against this SDK, treat `mask()` as the canonical pattern and the three wrappers as sugar.

```python
shield.mask(
    text: str,
    method: Literal["full_mask", "partial_mask", "redact", "tokenize"] = "full_mask",
    categories: list[str] | None = None,
    *,
    scope_id: str | None = None,
) -> ProtectionResult

shield.mask_json(payload, method=..., categories=..., *, scope_id=...) -> ProtectionJsonResult

shield.redact(text: str, categories: list[str] | None = None) -> ProtectionResult
shield.anonymize(text: str, categories: list[str] | None = None) -> ProtectionResult
shield.tokenize(text: str, scope_id: str | None = None, categories: list[str] | None = None) -> ProtectionResult
```

**The four methods** (AC3 of `docs/PLAN.md`; the server's literal values, not the
brief's `"full"`/`"partial"`):

| `method` | Effect |
| --- | --- |
| `"full_mask"` | Replaces the whole value with a fixed mask. |
| `"partial_mask"` | Keeps the project policy's configured `partial_mask_reveal` count of characters, masks the rest. |
| `"redact"` | Removes the value entirely and leaves a `[REDACTED]` marker; there is no way to recover the original from the response alone. |
| `"tokenize"` | Replaces the value with a stable placeholder (`[EMAIL_001]`); the real value exists only in the encrypted vault, recoverable only through `detokenize`. |

`categories`, when given, restricts the method override to only those categories (others
keep the project policy's own configured method); omit it to apply `method` to every
category PIIShield detects.

`mask_json` is `mask`'s JSON counterpart: it walks every string leaf of a nested payload
and protects each one, while the response's `protected_json` preserves the exact input
structure (same keys, same nesting, same array order; AC7). Only leaf string values ever
change.

`ProtectionResult`:

| Field | Type | Meaning |
| --- | --- | --- |
| `protected_text` | `str` | the transformed text; always safe to log, display or forward |
| `findings` | `list[Finding]` | what was acted on |
| `review_count` | `int` | how many findings were routed to the review queue |
| `scope_id` | `str` | the scope used for placeholder consistency; set on every call (server-assigned when you did not pass one) |

`ProtectionJsonResult` is the same shape with `protected_json: Any` instead of
`protected_text: str`.

Both raise `PolicyViolationError` (never silently pass the raw value through) when the
project's policy marks a detected category as required to be masked and a call's
`skip_categories` (used internally by `scan`) would leave it unmasked (AC10; see
"Exceptions" below). `mask`/`redact`/`anonymize`/`tokenize` always send a real masking
method as the override, never a skip, so this error is specific to `scan`'s internal use
of `skip_categories` on a required category.

### Tokenization scope consistency (AC4)

```python
first = shield.tokenize("rahul@example.com", scope_id="checkout-session-42")
second = shield.tokenize("rahul@example.com", scope_id="checkout-session-42")
assert first.protected_text == second.protected_text  # same placeholder
```

Pass the same `scope_id` string across calls (a request id, or a named session id your
application controls) to get placeholder consistency: the same input value tokenized
twice within one scope always yields the same placeholder, and two different values never
collide on the same placeholder. Omit `scope_id` and the server assigns a call-local one,
returned as `result.scope_id`; pass that value back on a later call to keep using the
same scope. `scope_id` is plain data the SDK forwards verbatim; it carries no authority
of its own (compare the vault-access grant below, which does).

### `detokenize` and the vault permission model (AC5, AC6)

```python
shield.detokenize(placeholder: str, scope_id: str) -> DetokenizeResult
```

`detokenize` is the **only** call in this SDK that can return an original sensitive value,
and it requires a permission separate from the base `api_key`: a **vault-access grant**.
Unlike the brief's suggestion of a separate API key, the real backend models this as a
grant on an existing user or API key (`POST /api/v1/vault/grants`, owner role only):

```python
# An owner grants vault access to a specific API key (once, out of band, e.g. via the
# dashboard or a direct call to POST /api/v1/vault/grants with {"api_key_id": "..."}).
# The SAME PIIShield(api_url, api_key, project_id) client then just works for detokenize
# once that key's grant exists; there is no separate vault_api_key parameter.
result = shield.detokenize(placeholder="[EMAIL_001]", scope_id="checkout-session-42")
print(result.value)  # the original email, restored
print(result.category)  # "contact"
```

A caller whose key has no vault-access grant gets `VaultPermissionError` on a 403 (the
server's error code `vault_access_required`), **never the original value and never a
hint of it** in the exception message or details (AC5). `VaultPermissionError` is a
subclass of `APIError`, so code that only catches `APIError` still sees it, but catch
`VaultPermissionError` specifically when you want to react differently (show "ask an
owner for vault access" instead of a generic error page):

```python
from euron_piishield import VaultPermissionError

try:
    result = shield.detokenize(placeholder, scope_id)
except VaultPermissionError:
    show_request_vault_access_prompt()
```

**The vault's encrypted mapping is never included in any response to a protect, document
or AI-gateway request** (AC6): only an explicit, authorized `detokenize` call ever
returns an original value, and the SDK's models reflect this by having no field anywhere
else that could carry one.

### AI gateway: `protect` and `restore` (AC9)

```python
shield.protect(prompt: str, scope_id: str | None = None) -> ProtectResult
shield.restore(scope_id: str, model_response_text: str) -> RestoreResult
```

```python
protected = shield.protect("My PAN is ABCDE1234F. Explain my tax record.")

# Send ONLY protected.protected_text to the external model.
model_response = call_external_model(protected.protected_text)

# Restore placeholders in the model's response for your own application.
restored = shield.restore(protected.scope_id, model_response)
print(restored.restored_text)   # the real PAN is back, for you only
```

#### AI gateway safety property

This is a real safety property, not just an API shape, and the SDK's types enforce it
structurally:

- `ProtectResult.protected_text` (`str`) is the only field meant to leave your process and
  reach an external model.
- `ProtectResult.scope_id` (`str`) is a **separate field**. It is not embedded in
  `protected_text`, not derivable from it, and not sent as part of the same payload a
  caller would forward to an external model (it has its own field on the result object).
  A caller who does `send_to_model(protected.protected_text)` cannot leak the scope id by
  that call alone, because it is simply not present in that value.
- `restore()` takes `scope_id` and the model's raw response text, and returns
  `RestoreResult.restored_text`, which is for **your calling application only**. The
  external model that produced `model_response_text` never sees `restored_text`; nothing
  in this SDK sends it anywhere.
- Keep `scope_id` server side (or, in a browser-facing app, with the backend that called
  `protect`, never shipped to client-side code that also talks to the model provider).
  Treat it like a credential-adjacent value: it is what lets the placeholders in a
  model's response be turned back into real data (the same vault, scoped by
  `(org, project, scope_id)`, that backs `tokenize`/`detokenize`).

If you find yourself writing `json.dumps({**protected.__dict__, "for_model": True})` or
similarly serializing the whole `ProtectResult`, stop: only ever serialize
`protected.protected_text` for the model-facing side of your integration.

### Documents: `protect_file`

```python
shield.protect_file(path_or_bytes: str | bytes | Path, filename: str | None = None) -> bytes
```

Protects a PDF, DOCX, XLSX or CSV file and returns the protected file in the **same
format** (never a plain-text dump), per `POST /api/v1/documents`. There is no separate
scan-only endpoint for documents (unlike text/JSON's `scan`/`mask` split): the server
returns the protected file directly as a binary body, with a
`Content-Disposition: attachment` header, not JSON. Write the returned bytes wherever the
original file came from:

```python
protected_bytes = shield.protect_file("invoice.pdf")
Path("invoice.protected.pdf").write_bytes(protected_bytes)
```

An unrecognised extension raises `UnsupportedFileTypeError` before any request is sent.

### Database scan

```python
shield.scan_database(
    connection_string: str, table_name: str, engine: str = "postgres", *, sample_rows: int = 200
) -> DatabaseScanResult
```

A read-only, column-level scan against a provided Postgres, MySQL or SQLite connection:
samples `sample_rows` rows of `table_name` and reports which columns look like they hold
PII, with confidence, for a human to act on. The connection string is used once and never
stored (not in the result row, not in the audit log); only `table_name` and the column
findings persist. 0.1.0 does not write back to or anonymize a live database (see
`docs/PLAN.md`'s Scope section; that is a roadmap feature with its own safety review).

### Policies, audit logs, review queue

```python
shield.get_policy() -> Policy
shield.set_policy(
    *,
    required_categories: list[str] | None = None,
    masking_method: dict[str, str] | None = None,
    partial_mask_reveal: int = 4,
    confidence_threshold: float = 0.6,
    retention_days: int = 90,
) -> Policy

shield.get_audit_logs(*, limit: int = 50, action: str | None = None) -> AuditLogPage
shield.get_review_items() -> list[ReviewItem]
shield.approve_review_item(item_id: str) -> ReviewItem
shield.dismiss_review_item(item_id: str) -> ReviewItem
```

Policies are per-project, singular (`GET`/`PUT /api/v1/projects/{project_id}/policy`),
not a list you create many of: `set_policy` always replaces the whole policy.

`AuditLogEntry` deliberately has no field that could hold an original value
(`finding_count` and `categories` only, never a value): the audit log records that a
protect, detokenize or document call happened, never what it found or restored (AC11).

## Exceptions

```
PIIShieldError                      base of every exception this SDK raises
├── APIError                        PIIShield answered with a non-2xx error response
│   ├── VaultPermissionError        403 "vault_access_required" specifically on detokenize (AC5)
│   └── PolicyViolationError        422 "required_category_unmasked": a required category would be left unmasked (AC10)
└── ConnectionError                 PIIShield could not be reached, OR answered 503 "dependency_unavailable"

UnsupportedFileTypeError(PIIShieldError)   protect_file given an unrecognised extension
```

- **`PIIShieldError`**: catch this to mean "something went wrong talking to PIIShield,"
  broadly.
- **`APIError`**: has `.message`, `.status_code`, `.code` (the server's error code
  string, from `{"error": {"code", "type", "message", "details"}}`) and `.details` (a
  dict). Raised for any non-2xx response that is not one of the two subclasses below.
- **`VaultPermissionError`**: a 403 with error code `vault_access_required`, from
  `detokenize`. Never carries the original value or a hint of it.
- **`PolicyViolationError`**: a 422 with error code `required_category_unmasked`: a
  protect call was refused because a required category would be left unmasked; the call
  fails outright rather than silently returning the raw value for that category.
- **`ConnectionError`** (this module's own, not Python's builtin of the same name):
  raised when the request never got a response at all (DNS failure, connection refused,
  timeout), **or** when the server itself answered with a 503
  `dependency_unavailable` (Postgres, Redis or the mock AI service is down: the server's
  own contract is a clear, retryable failure, never a response that silently omits
  findings, so the SDK treats both as the same connection-shaped failure for callers that
  retry on it).
- **`UnsupportedFileTypeError`**: raised client side, before any request, when
  `protect_file` cannot infer a content type for the given filename.

```python
from euron_piishield import APIError, PolicyViolationError, VaultPermissionError

try:
    result = shield.detokenize(placeholder, scope_id)
except VaultPermissionError:
    ...  # this API key's grant does not cover the vault; ask an owner
except PolicyViolationError:
    ...  # unreachable here (detokenize never raises this); shown for contrast with mask
except APIError as exc:
    log.error("piishield call failed: %s (%s)", exc.message, exc.code)
```

## Wire format

**This section documents the HTTP request and response shapes this SDK uses**, confirmed
directly against the real `apps/api/src/piishield` source (its routers and Pydantic
schemas), not the product brief's own illustrative endpoint names. The brief suggested
`/api/v1/scan/text`, `/api/v1/mask`, `/api/v1/tokenize`, `/api/v1/detokenize`,
`/api/v1/ai/protect`, `/api/v1/ai/restore`: the real backend instead has
`detectors/scan` (a dedicated, side-effect-free detection route), `protect/text`,
`protect/json` (one endpoint covers every protection method, including a scan-shaped call
via `skip_categories`, which is what `scan_json` uses since there is no dedicated JSON
scan route), `vault/detokenize`, `ai-gateway/protect`, `ai-gateway/restore`, plus
`documents`, `database-scan`, `projects/{id}/policy`, `audit` and `review`. This SDK's
method names stay close to the brief (`scan`, `mask`, `redact`, `anonymize`, `tokenize`,
`detokenize`, `protect`, `restore`) for API familiarity, while their HTTP implementation
follows the real routers.

All requests carry `Authorization: Bearer <api_key>` and a
`User-Agent: euron-piishield-python/<version>` header. JSON request and response bodies
throughout; `protect_file` sends `multipart/form-data` with a `file` field and
`project_id` as a query parameter, and receives the protected file as a raw binary body
(not JSON).

| Method | HTTP | Request body | Response body |
| --- | --- | --- | --- |
| `scan(text)` | `POST /api/v1/detectors/scan` | `{project_id, text}` | `{findings, review_count}` (always `0`; the route never enforces policy) |
| `scan_json(payload)` | `POST /api/v1/protect/json` | `{project_id, payload, skip_categories: [every category]}` | `{protected, findings, review_count, scope_id}` |
| `mask(text, method, categories, scope_id)` | `POST /api/v1/protect/text` | `{project_id, text, method_overrides: {category: method, ...}, scope_id?}` | `{protected, findings, review_count, scope_id}` |
| `mask_json(...)` | `POST /api/v1/protect/json` | `{project_id, payload, method_overrides, scope_id?}` | `{protected, findings, review_count, scope_id}` |
| `redact`/`anonymize`/`tokenize` | same as `mask`, with `method` fixed | same shape as `mask`, `method_overrides` built from the fixed method | same shape as `mask` |
| `detokenize(placeholder, scope_id)` | `POST /api/v1/vault/detokenize` | `{project_id, placeholder, scope_id}` | `{placeholder, value, category}` |
| `protect(prompt, scope_id)` | `POST /api/v1/ai-gateway/protect` | `{project_id, prompt, scope_id?}` | `{protected_prompt, findings, scope_id}` |
| `restore(scope_id, model_response_text)` | `POST /api/v1/ai-gateway/restore` | `{project_id, scope_id, model_response}` | `{restored_response, placeholders_restored}` |
| `protect_file(path, filename)` | `POST /api/v1/documents?project_id=...` (multipart) | file field `file` | raw protected file bytes, `Content-Disposition: attachment` |
| `scan_database(...)` | `POST /api/v1/database-scan` | `{project_id, engine, connection_string, table_name, sample_rows}` | `{id, table_name, rows_sampled, columns: [{column, category, confidence, sample_hits}]}` |
| `get_policy()` | `GET /api/v1/projects/{project_id}/policy` | - | `{id, project_id, required_categories, masking_method, partial_mask_reveal, confidence_threshold, retention_days}` |
| `set_policy(...)` | `PUT /api/v1/projects/{project_id}/policy` | `{required_categories, masking_method, partial_mask_reveal, confidence_threshold, retention_days}` | same shape as `get_policy` |
| `get_audit_logs(**params)` | `GET /api/v1/audit?limit=&action=` | query params | `{items: [AuditEntry...], next_cursor}` |
| `get_review_items()` | `GET /api/v1/review?project_id=...` | query param | `[ReviewItem...]` |
| `approve_review_item(id)` | `POST /api/v1/review/{id}/approve` | `{}` | `ReviewItem` |
| `dismiss_review_item(id)` | `POST /api/v1/review/{id}/dismiss` | `{}` | `ReviewItem` |

**Finding** (embedded in every protect/scan response), matching
`protection.schemas.ProtectedFindingOut` exactly:

```json
{
  "category": "contact",
  "start": 7,
  "end": 29,
  "confidence": 0.95,
  "checksum_valid": null,
  "recognizer": "email",
  "method": "full_mask",
  "placeholder": null,
  "in_review": false
}
```

**Error body** (any non-2xx response), matching `piishield.core.errors.AppError.body`:

```json
{"error": {"code": "required_category_unmasked", "type": "policy_error", "message": "...", "details": {"category": "government_id"}}}
```

The SDK maps a 403 with `code == "vault_access_required"` to `VaultPermissionError`, a
422 with `code == "required_category_unmasked"` to `PolicyViolationError`, and a 503
(always `code == "dependency_unavailable"` from this server) to `ConnectionError`.
Every other non-2xx response becomes a plain `APIError`.

**Confirmed directly from source** (so nothing here is a guess pending reconciliation):
`apps/api/src/piishield/protection/{router,schemas,service}.py`,
`detectors/schemas.py`, `vault/{router,schemas,service}.py`,
`ai_gateway/{router,schemas}.py`, `documents/{router,schemas}.py`,
`database_scan/{router,schemas}.py`, `policies/{router,schemas,service}.py`,
`audit/{router,schemas}.py`, `review/{router,schemas}.py`,
`auth/{router,schemas,dependencies}.py`, `core/errors.py`.

**What is still genuinely open** (the backend's app factory, `main.py`, does not exist
yet as of this SDK pass, so nothing below has been exercised against a live server):

1. The exact confidence score and `recognizer` name each detector assigns for a given
   match (the category, span and checksum result are confirmed from the schema and
   service code; the specific numbers in `sdks/testdata/scan-fixture.json` are this SDK's
   own best estimate, clearly marked as such in that file's `about` field).
2. Whether the detectors package (`piishield.detectors`) is fully wired into the
   `protection` router by the time the app runs (`detectors/schemas.py` exists but there
   was no `detectors/router.py`; detection is invoked through
   `protection.service.run_scan`, which imports `detectors.service.scan` directly).
3. Rate limiting, pagination cursor format for `get_audit_logs`'s `next_cursor` (the
   schema allows `str | None` but no router code paginates past the first page yet).

## Development

```bash
uv sync                                                        # Python 3.10+ dev environment
uv run pytest tests/unit                                       # mocked HTTP, no network
PIISHIELD_API_URL=http://localhost:5530 PIISHIELD_API_KEY=... PIISHIELD_PROJECT_ID=... \
  uv run pytest tests/integration                               # a real, running API
uv run ruff check src tests && uv run ruff format --check src tests
uv run mypy src tests
uv build                                                        # wheel and sdist into dist/
```

The shared cross-language fixture at `../testdata/scan-fixture.json` (generated by
`../testdata/generate_fixture.py`) is loaded by `tests/unit/test_fixture_parity.py` to
prove this SDK's response parsing agrees with the Node SDK's (AC14 of `docs/PLAN.md`).
