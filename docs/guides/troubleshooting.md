# Troubleshooting

## "A number that looks like a card/Aadhaar/SSN isn't being flagged"

This is very likely correct behavior, not a bug. Every card, Aadhaar, IBAN, PAN and US SSN
recognizer validates its match against a real checksum (Luhn, Verhoeff, ISO 7064 mod 97,
the PAN entity-character rule, SSA area/group/serial sanity rules respectively, see
`apps/api/src/piishield/detectors/checksums.py`) before it is ever reported. A value that
fails its checksum is dropped entirely, not reported at low confidence. This is
acceptance criterion 2's core guarantee: a random 16-digit string is not a credit card
just because it has 16 digits. If you believe a genuinely valid number is being missed,
check the exact format first (spacing, dashes, country code), since the pattern itself
still has to match before the checksum is even evaluated.

## "`POST /api/v1/vault/detokenize` returns 403"

The caller does not hold the vault-access permission, which is separate from role and from
API key scope (acceptance criterion 5): an `owner`, an `admin`, and even a write-scoped API
key do not get vault access automatically. An organisation owner grants it explicitly:

```
POST /api/v1/vault/grants
{ "user_id": "...", }        # or "api_key_id": "..."
```

(owner role required). See [security.md](../architecture/security.md)'s "The vault-access
permission" section. The error message itself says this
(`"This action needs vault access, which is granted separately from your role"`); if you
are seeing a different error, you likely have a different problem (check `scope_id` and
`placeholder` match an entry that actually exists in that scope first,
`PlaceholderNotFoundError` is a 404, not a 403).

## "I changed a policy and the next protect call still used the old settings"

The project policy cache has a deliberate, bounded staleness window, default 5 seconds
(`POLICY_CACHE_TTL_S`). A write bumps a version stamp every replica checks on its next
request, so the change becomes visible within that window, not instantly. See
[ADR-0002](../architecture/adr/0002-bounded-staleness-policy-cache.md). If it has been
longer than the TTL and you still see the old policy, check you updated the right project
(`project_id`), and that the write actually succeeded (a `PUT` to another organisation's
`project_id` correctly 404s rather than silently creating a dangling policy, see
`policies/service.py upsert`).

## "The API fails to boot with `KEY_MODE=kms`"

This is expected: `key_mode=kms` is explicitly not implemented in 0.1.0.
`core/sealing.py build_sealer` raises `NotImplementedError` on purpose rather than
silently falling back to a weaker key backend. Use `KEY_MODE=local` (the default) with a
real `LOCAL_MASTER_KEY`. See [ADR-0001](../architecture/adr/0001-envelope-encryption-local-key-only.md)
and, if you hit this while deploying to AWS,
[deploy-aws.md](deploy-aws.md)'s callout about `aws-dev`/`aws-prod`'s Terraform currently
setting `KEY_MODE=kms` by default.

## "The audit log seems to stop at 200 entries"

It does, in 0.1.0: `GET /api/v1/audit` caps `limit` at 200 and `next_cursor` is always
`null`. There is no pagination past that cap yet; see
[security.md](../architecture/security.md) and [operations.md](operations.md) for this
stated as a known limitation. Every entry is still written to Postgres, only unreachable
through this endpoint past the cap.

## "The API fails to boot in production with a config error"

`Settings.guard()` only runs when `ENVIRONMENT=production`, and lists every problem it
finds in one `RuntimeError`: an under-length or default `SESSION_SECRET`/`API_KEY_PEPPER`/
`LOCAL_MASTER_KEY`, a `CORS_ORIGINS` containing `*`, or `COOKIE_SECURE` not `true`. Read
the full message, it names every field that needs fixing at once. See
[configuration.md](configuration.md)'s "Production boot guard" section.

## "`make up` fails with a port already in use"

Another process on your machine is already bound to one of PIIShield's local ports (web
5510, api 5530, postgres 5542, redis 5579, floci 5566, mailpit 5525, mock AI 5550). Set
the matching `PS_*_PORT` variable in `deploy/compose/.env` to a free port, or stop the
other process. Never 3000, 3001, 5060, 4040 or 8081, reserved by other work on this
program.

## "`make down` deleted my data"

By design: `make down` removes the stack's local Docker volumes (Postgres, Redis, exports,
Floci state) along with the containers. Run `make backup` before `make down` if you need
to keep anything, and `make restore BACKUP=backups/<timestamp>` afterward. See
[operations.md](operations.md).

## "Puppeteer QA (`make qa`) can't sign in"

PIIShield's dashboard has no session cookie; it keeps a bearer token in `localStorage`
(`piishield.auth`, zustand persist format). `make qa`/`make demo` need to run against a
stack that already has the demo organisation seeded (`make demo`); signing in before that
fails because the demo user does not exist yet. A sign-in that returns HTTP 429 means the
per-IP rate limit on `/api/v1/auth/login` was hit; the script backs off and retries
automatically, but repeated manual sign-in attempts can trigger it too.
