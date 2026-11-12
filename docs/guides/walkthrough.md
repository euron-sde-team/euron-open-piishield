# Walkthrough

A tour of the dashboard with the seeded demo organisation (`make up && make demo`), owner
login `priya.nair@verdantpay.example` / `Demo-Owner-Pass-1`. Every page below is real:
`http://localhost:5510<path>`.

## Sign in

`/login`. Sign in with the demo owner above, or `/signup` to create a new organisation and
owner. The dashboard keeps its session as a bearer token (there is no cookie), so signing
out simply clears it.

## Overview (`/`)

Org-wide totals across every project: scans run, findings detected, items waiting on
review, and values held in the vault, plus a findings-by-category breakdown (`contact`,
`financial`, `government_id`, `credential`, `personal`). A project switcher at the top
scopes everything below it to one project at a time.

## Scan Center (`/scan`)

Paste text (or upload a document, see below) and scan it. The result lists every finding
with its category, the matched span highlighted in the text, a confidence score, and, for
checksum-backed categories, whether the checksum passed. Choose a protection method per
category (full mask, partial mask, redact, tokenize) or accept the project's policy
defaults, and see the protected output rendered next to the original. This is the
dashboard's version of `POST /api/v1/protect/text`, see
[quickstart-local.md](quickstart-local.md) for the same call from the command line.

## Review Queue (`/review`)

Findings that landed below the project's confidence threshold (and were left unprotected,
unless their category was also marked required, acceptance criteria 10 and 13). Each item
shows category, span, confidence and which recognizer matched, never the original matched
text (acceptance criterion 11's no-raw-value guarantee extends here too). Approve a finding
to confirm it is real PII, or dismiss it as a false positive; either decision is recorded
in the audit log.

## Documents (`/documents`)

Upload a PDF, DOCX, XLSX or CSV. The response is a protected copy of the same file format,
not a text dump: every detected value across every page, paragraph, sheet or row is masked,
redacted or tokenized per the request, and a per-page/sheet breakdown of what was found
accompanies the download (acceptance criterion 8).

## Database Scan (`/database-scan`)

Supply a connection string (Postgres, MySQL or SQLite) for a read-only, column-level scan:
PIIShield samples rows and reports which columns look like they hold PII, with a
confidence per column, for a human to act on. It never writes back to or modifies the
scanned database, and the connection string itself is never persisted, only the findings.

## AI Gateway (`/ai-gateway`)

A demonstration of the protect-then-restore round trip an AI-calling application would
perform around an external model call: paste a prompt, see it protected (every category
tokenized, regardless of the project's own masking policy, since only tokenization allows
restoring the exact value afterward) along with the `scope_id` the call returns, then paste
a mock "model response" containing one of the returned placeholders and restore it back to
the original value, scoped to that exact `scope_id` (acceptance criterion 9). This restore
call is a different trust boundary from the vault's `detokenize`, see
[security.md](../architecture/security.md): it does not require the vault-access
permission, because it is completing a round trip the caller itself started.

## Token Vault (`/vault`)

Visible to everyone, but detokenizing a value requires the vault-access permission, a
grant separate from role and from API key scope (acceptance criterion 5). As the demo
owner (who by default does not automatically have vault access either, consistent with
acceptance criterion 5), grant yourself access from **API Keys** or **Settings**, or sign
in as a seeded user who already has it, then resolve a placeholder back to its original
value here. A caller without the grant sees a 403 explaining that vault access is separate
from their role, never the value and never a hint of it.

## Policies (`/policies`)

Per-project configuration: which categories are required (always protected regardless of
confidence), the masking method per category, the confidence threshold below which a
finding goes to the Review Queue, and the retention period for scan records and vault
entries. A change here takes effect across every API replica within the policy cache's
bounded staleness window (default 5 seconds, see
[ADR-0002](../architecture/adr/0002-bounded-staleness-policy-cache.md)).

## API Keys (`/keys`)

Create, list and revoke project API keys (`pii_<prefix>_<secret>`), each with `read` or
`write` scope. The full key is shown once, at creation. Grant or revoke vault access to a
specific key from here as well (owner role required for both).

## Audit Log (`/audit`)

Every scan, mask, redact, tokenize, detokenize, policy change and vault-access change,
with who did it, when, how many findings, and which categories, never an original value
(acceptance criterion 11). Capped at the most recent 200 entries in 0.1.0, see
[operations.md](operations.md).

## Settings (`/settings`)

Organisation-level settings, members and their roles (`owner`, `admin`, `viewer`), and
each member's vault-access flag.
