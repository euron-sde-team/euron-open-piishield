#!/usr/bin/env bash
# Restore a backup made by scripts/backup.sh into the running local stack. Replaces the
# database contents. Stops the api and the web app first so nothing writes while the
# database is replaced.
#   make restore BACKUP=backups/<timestamp>
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${1:?usage: scripts/restore.sh backups/<timestamp>}"
[[ "$SRC" = /* ]] || SRC="$ROOT/$SRC"
[[ -f "$SRC/piishield.dump" ]] || { echo "no piishield.dump in $SRC"; exit 1; }
COMPOSE=(docker compose --env-file "$ROOT/deploy/compose/.env" -f "$ROOT/deploy/compose/compose.yaml" -f "$ROOT/deploy/compose/compose.floci.yaml")

"${COMPOSE[@]}" stop web api
"${COMPOSE[@]}" exec -T postgres pg_restore -U piishield -d piishield --clean --if-exists --no-owner < "$SRC/piishield.dump"
"${COMPOSE[@]}" up -d --wait api web
echo "restored ${SRC#"$ROOT"/}"
