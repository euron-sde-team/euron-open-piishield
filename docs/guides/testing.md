# Testing

Every gate below runs locally against Docker; none of it touches a real AWS account. Real
counts from the most recent full run (2026-11-12) are given so this page says what the
suite actually proves rather than what it is supposed to prove.

## Static

```sh
make lint        # ruff check + ruff format --check (api), eslint (web)
make typecheck    # mypy --strict (api), tsc --noEmit (web)
```

## Unit tests

```sh
make test    # pytest tests/unit (api), vitest (web)
```

No network, no database. Most recent run: **108 backend tests passed, 86% line coverage**
on `apps/api/src`; **40 web dashboard unit tests**.

## Integration tests

```sh
make test-integration
```

Runs `pytest tests/integration -m integration` against the real Postgres, Redis and mock
AI service in the Compose stack (started automatically if not already running), covering
every endpoint, auth and authorization path (including the vault-access permission check
and tenant isolation), and the failure paths the acceptance criteria call out (a required
category refused unmasked, detokenize without vault access refused, cross-org lookups
returning 404).

## Test matrix

```sh
make test-matrix
```

Runs the integration suite under every backend combination PIIShield's own code actually
branches on in 0.1.0: `kv=redis` and `kv=memory` (`core/kv.py`'s `create_kv`, an empty
`REDIS_URL` falls back to `MemoryKV`, used for the policy cache and the tokenization scope
map). **2 of 2 combinations passed.** An earlier version of this script also ran a
`storage=s3, KEY_MODE=kms` leg; it was removed because 0.1.0 has no S3 storage backend and
`sealing.py` deliberately raises `NotImplementedError` for `key_mode=kms`, so that leg
could only ever fail for a reason unrelated to the code under test. See
`scripts/test-matrix.sh`'s own comment.

## SDK tests

```sh
cd sdks/python && uv run pytest
cd sdks/node && pnpm test
```

Most recent run: **Python SDK, 53 unit tests plus 5 live integration tests** (against a
running API); **Node SDK, 27 unit tests plus 5 live integration tests**. A shared fixture
under `sdks/testdata` asserts byte-identical protected output between the two SDKs and the
raw REST API (acceptance criterion 14).

## OpenAPI drift

```sh
make openapi
```

Regenerates `docs/api/openapi.yaml` from the live FastAPI app
(`piishield openapi`). Committed output must match a fresh export; a mismatch means a
route or schema changed without the docs being regenerated.

## End-to-end (Playwright)

```sh
make e2e
```

Against `make up && make demo`'s full stack: sign in, scan a text sample in the Scan
Center, see findings with confidence scores, choose a masking method and see the protected
output, open the Token Vault and detokenize a value as an authorized user, open the Review
Queue and act on a low-confidence finding, run the AI Gateway's protect/restore flow.
**14 tests, run twice clean** on the most recent verification pass.

## Browser QA (Puppeteer)

```sh
make qa
```

Visits every dashboard page (Overview, Scan Center, Review Queue, Documents, Database
Scan, AI Gateway, Token Vault, Policies, Audit Log, API Keys, Settings, plus the anonymous
login/signup pages) in light and dark mode at desktop and phone width, and fails on console
errors, failed or 4xx/5xx network requests, broken images, horizontal overflow, or an
unexplained empty state. Most recent run: **52 page views (13 pages times 2 themes times
2 sizes), 0 problems.**

## Infrastructure

```sh
make tf-validate     # terraform validate, every env, no backend/credentials needed
make tf-lint         # tflint, every module and env
make tf-security     # checkov policy scan
make tf-aws-on-floci  # full aws-dev apply/re-plan/destroy against a throwaway Floci
```

Most recent run: `tf-validate` clean across all 3 environments (`local-floci`, `aws-dev`,
`aws-prod`); `tflint` clean; `checkov` **319 passed, 0 failed**; `tf-aws-on-floci`
completed a full apply, re-plan and destroy of the `aws-dev` environment against a
throwaway Floci, **173 resources**, with **zero adds or replacements on re-plan** (the only
drift was the expected Floci-non-persisted-attribute kind, not a real plan difference).
`local-floci`'s own one-shot Terraform apply also runs on every `make up`.

## Sanitization

```sh
make sanitize
```

Scans every committable file for secrets, cloud account identifiers, unresolved `.env`
values, and em or en dashes (U+2014, U+2013), which are banned everywhere in this
program's repositories. Most recent run: clean.

## Purpose check

Every acceptance criterion in [docs/PLAN.md](../PLAN.md) maps to a specific automated
test; see that document's "Release verification" table for the full mapping (for example,
acceptance criterion 4's scope-consistent tokenization is
`test_vault.py::test_ac4_consistent_tokenization_within_scope`, and acceptance criterion
11's audit log guarantee is `test_audit.py::test_ac11_audit_log_never_contains_a_real_value`).
