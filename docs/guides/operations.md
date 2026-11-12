# Operations

## Health and readiness

- `GET /healthz`: the process is up.
- `GET /readyz`: the process can reach its dependencies (Postgres, and Redis when
  configured).
- `GET /metrics`: Prometheus metrics. `piishield_scans_total{source}` (detection calls
  by `detectors_scan`/`text`/`json`/the AI gateway's source labels),
  `piishield_findings_total{category}` (findings by the five coarse categories),
  `piishield_protected_total{method}` (findings actually masked, redacted or tokenized,
  never counting a `skip`), `piishield_detokenize_total{outcome}` (`found`/`not_found`,
  never incremented for a 403: the `VaultAccess` dependency refuses those before this
  code runs).

Point your orchestrator's liveness probe at `/healthz` and readiness probe at `/readyz`;
restarting a process that fails `/healthz` is always safe, restarting one only failing
`/readyz` usually is not (it may just mean a dependency is briefly down).

## Logs

Structured JSON, one line per request, including a request id. Locally:

```sh
make logs SERVICE=api        # or web, mockai, migrate, tf-local-floci, floci, mailpit
make ps                      # stack status
```

## The dashboard summary

There is no separate worker or rollup table: the Overview page's scan counts, findings
by category and pending-review counts are a live Postgres aggregate query
(`reports/service.py`), behind a 15-second Redis (or in-process memory) response cache
keyed by org id. A cache miss costs one set of aggregate queries, not a scan of every
row in `scan_events`.

## Backup and restore

```sh
make backup                       # Postgres dump, into backups/
make restore BACKUP=backups/<timestamp>
```

0.1.0 has nothing else durable to back up: a document upload's protected bytes are
returned directly in the response and never written to disk or S3
(`documents/service.py`), so the Postgres dump is the whole picture.

Run `make backup` before anything that could affect the database (an upgrade, a manual
migration, a key rotation). `backups/` is gitignored; move backups off the host per your
own retention policy, the project does not manage offsite storage for you.

## Stopping the stack

```sh
make down
```

Stops every container **and deletes the stack's local Docker volumes** (Postgres, Redis,
exports, Floci data, Terraform state), except the Terraform provider plugin cache, which
survives so the next `make up` does not re-download providers. Run `make backup` first if
you need to keep anything.

## Rotating secrets

- `SESSION_SECRET`: rotating it invalidates every existing dashboard session immediately
  (every session is a token signed with it).
- `API_KEY_PEPPER`: rotating it invalidates every existing API key's stored hash; every
  key would need to be reissued. Plan a maintenance window for this one.
- `LOCAL_MASTER_KEY`: rotating it requires re-sealing every `vault_entries` row under the
  new key; 0.1.0 has no automated migration for this yet (see
  [ADR-0001](../architecture/adr/0001-envelope-encryption-local-key-only.md)'s
  consequences section). Treat a planned rotation as a manual, scripted migration task,
  and back up first.

## Known 0.1.0 operational limitations

- **The audit log is capped at 200 entries per request, with no pagination past it.**
  `audit.service.list_entries` enforces `min(limit, 200)` and the API's `next_cursor` is
  always `null`. An organisation with more history than that sees only the most recent 200
  matching entries through `GET /api/v1/audit`. This is a real gap to plan around
  operationally (export older data by other means if you need a longer-lived record today)
  and not a data-loss bug: every row is still written and still in Postgres, only
  unreachable through this endpoint past the cap. See
  [security.md](../architecture/security.md).
- **No automated alerting.** `MAIL_BACKEND` exists for a future notifier; 0.1.0's review
  queue and reports are pull (visit the dashboard), not push.
- **The policy cache has a bounded 5-second staleness window** by design
  ([ADR-0002](../architecture/adr/0002-bounded-staleness-policy-cache.md)): a policy change
  on one replica is visible to every replica within that window, not instantly. This is
  rarely operationally relevant, but matters if you are debugging "why didn't my policy
  change apply immediately."

## Scaling

The API is stateless; run as many replicas as you like behind a load balancer, state
lives in Postgres and (optionally) Redis. Without Redis, the policy cache and
tokenization scope map are per-process, which is correct but not shared across replicas,
see [configuration.md](configuration.md)'s `redis_url` entry. Size `db_pool_size` and
`db_max_overflow` so `api replicas x (pool + overflow)` stays under your database's
`max_connections`.
