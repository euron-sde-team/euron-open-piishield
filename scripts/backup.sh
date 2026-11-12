#!/usr/bin/env bash
# Back up the local stack: a consistent Postgres dump (organizations, projects, policies,
# scan_events, findings, vault_entries, review_items, database_scan_results, audit_log).
# 0.1.0 has no S3 export storage to back up: a document upload's protected bytes are
# returned directly in the response and never written to disk or S3 (documents/service.py),
# so there is nothing durable outside Postgres. Writes backups/<timestamp>/ next to the
# repository.
#   make backup              # then: make restore BACKUP=backups/<timestamp>
# On AWS use RDS snapshots instead (docs/guides/operations.md).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE=(docker compose --env-file "$ROOT/deploy/compose/.env" -f "$ROOT/deploy/compose/compose.yaml" -f "$ROOT/deploy/compose/compose.floci.yaml")
DEST="$ROOT/backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$DEST"

# pg_dump runs in one transaction, so the dump is consistent while the app keeps serving.
"${COMPOSE[@]}" exec -T postgres pg_dump -U piishield -d piishield --format=custom > "$DEST/piishield.dump"

echo "backup written to ${DEST#"$ROOT"/} ($(du -sh "$DEST" | cut -f1))"
