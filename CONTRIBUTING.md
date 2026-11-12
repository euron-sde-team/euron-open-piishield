# Contributing

Thanks for helping improve Euron Open PIIShield. This guide covers the workflow, the bar a
change has to clear, and the conventions the codebase follows.

## Ground rules

- **Open an issue first** for anything larger than a bug fix or a docs tweak, so we can
  agree on the approach before you invest time.
- **One concern per pull request.** A refactor and a feature are two PRs.
- **Security issues go through private reporting**, never a public issue. See
  [SECURITY.md](SECURITY.md).
- By contributing you agree your work is released under the [MIT License](LICENSE).

## Development setup

Requirements: Docker, Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 22 and
pnpm 9 (`corepack enable`).

```bash
make up          # Postgres, Redis, Floci (provisioned by Terraform), mock AI, api, web
make demo        # a seeded organisation: projects, policies, scans, findings, vault entries
make test        # unit tests (API and web)
```

[docs/guides/quickstart-local.md](docs/guides/quickstart-local.md) walks through the local
stack and your first protected scan in detail.

## Before you open a pull request

Each of these must pass:

```bash
make lint typecheck test
make test-integration                  # the API against real Postgres, Redis and the mock AI
make test-matrix                       # when you touched detectors, protection, vault or policies caching
make e2e                               # when you touched a dashboard flow
make tf-validate tf-lint tf-security   # when you touched infra/terraform
make tf-aws-on-floci                   # same: apply, re-plan and destroy aws-dev against Floci
make openapi                           # when you changed an endpoint (checked for drift)
make sanitize                          # no credentials, account ids, resource ids or dashes
```

## Conventions

**Package by domain.** `apps/api/src/piishield/<domain>/` owns its `router.py` (HTTP only,
no detection logic, no SQL), `schemas.py` (the public contract), `service.py` (the
business rules), `repository.py` (the only code that queries the DB for that domain) and
`models.py`. Dependencies point inward: router, service, repository, models. A domain
calls another domain's **service**, never its repository or models directly. The one
documented exception is `ai_gateway.service.restore` calling `vault.service.
resolve_in_scope` directly, because `restore` is a deliberately different trust boundary
from the vault's own `detokenize`, explained in that module's docstring and in
[docs/architecture/LLD.md](docs/architecture/LLD.md).

**A finding never carries its matched text out of the detector.** `Finding.as_dict()`
deliberately excludes `matched_text`; every response-shaping function uses `as_dict()` or
builds its own shape from the dataclass fields that are safe to expose, never the raw
dataclass with `matched_text` attached. A new endpoint that returns findings must follow
this same pattern. The audit log, scan records, review items, document scans and database
scan results all store only counts, categories, spans and confidence, never a value; keep
it that way, see [docs/architecture/data-model.md](docs/architecture/data-model.md)'s
"what is deliberately never stored" section.

**Vault access is never implied.** If a new code path needs to read a vault entry's
plaintext, it goes through the `VaultAccess` FastAPI dependency
(`auth/dependencies.py`), never through role or API key scope alone, and never by calling
`Sealer.open` directly from outside `vault/service.py` unless you are writing the AI
gateway's documented exception.

**A checksum failure means "not this category," not "low confidence."** When adding a
recognizer with a real checksum, a failed check must make `rec.check()` return
`(False, ...)` so the match is dropped entirely, not reported with a lower confidence
score. See `detectors/recognizers.py` and `detectors/checksums.py`.

**Overlap resolution is ordered, most specific first.** A new recognizer's position in
`RECOGNIZERS` decides whether it can steal a span from another recognizer. Read
[ADR-0003](docs/architecture/adr/0003-fixed-priority-overlap-resolution.md) before adding
one, and place it relative to existing entries deliberately, with a comment if the
placement is not obvious from confidence alone.

**External key material sits behind a Protocol.** Key sealing (`Sealer`: `seal`/`open`) is
the only one in 0.1.0; a future KMS backend implements the same two methods and is chosen
by `key_mode`, never a call-site branch. See
[ADR-0001](docs/architecture/adr/0001-envelope-encryption-local-key-only.md).

**Configuration is validated.** A new setting goes in `core/config.py`, is documented in
[docs/guides/configuration.md](docs/guides/configuration.md) in the same PR, and
security-relevant ones are enforced by `Settings.guard()` at boot.

**Database changes are new migrations.** Add an Alembic revision under
`apps/api/src/piishield/migrations/versions/`. Never edit an applied one. Indexes for every
new filter the API exposes belong in the same revision.

**The caching layers are documented, not incidental.** The policy snapshot cache, the
tokenization scope map, and the dashboard aggregate cache are each described in
[docs/architecture/HLD.md](docs/architecture/HLD.md)'s caching table. A change to any of
them (TTL, invalidation trigger, key shape) updates that table in the same PR, and keeps
the never-fail-closed property: a KV outage must degrade to a slower, still-correct path
(a database read, a vault lookup), never block a scan or protect call. See `core/kv.py`'s
own docstring.

**Comments explain why.** The code says what it does. Comments are for the constraint, the
incident, or the trade-off that made it this way.

**Style.** ruff and mypy `--strict` for Python; ESLint and TypeScript strict for the web.
No em dashes or en dashes anywhere, in code, comments, docs, commit messages or PR text
(the sanitization check enforces it; use a colon, a comma, parentheses, a period, or "to"
for a range instead).

## SDKs

`sdks/python` and `sdks/node` must stay wire-compatible with the API and with each other:
both expose `scan`, `mask`, `redact`, `tokenize`, `detokenize` and the AI gateway's
`protect`/`restore`, and both reason only about the five coarse categories (`contact`,
`credential`, `financial`, `government_id`, `personal`) on the wire, never a per-recognizer
name (that is the `recognizer` field, metadata, not a dimension either SDK branches on). A
shared fixture under `sdks/testdata` asserts byte-identical protected output between both
SDKs and the raw REST API; a change to the wire format needs a fixture update and must pass
in both SDK test suites.

## Commit messages

Imperative mood with an optional scope: `vault: confirm the cached placeholder's row still
exists before trusting it`, `web: show checksum status on a finding`. Explain the why in
the body when it is not obvious. No em dashes or en dashes.

## Architecture decisions

Significant decisions are recorded in
[docs/architecture/adr/](docs/architecture/adr/). If your change reverses or extends one,
add a new ADR rather than editing the old one.
