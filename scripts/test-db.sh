#!/usr/bin/env bash
# Make sure the services the integration suite talks to are reachable: Postgres, Redis
# and the mock AI/LLM service.
# Reuses the Compose services when the stack is up; otherwise starts just those. Tests
# never use a host-installed Postgres or Redis.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/deploy/compose/.env"
port() { local v; v="$(grep -s "^$1=" "$ENV_FILE" | cut -d= -f2 || true)"; echo "${v:-$2}"; }

ready() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }

missing=()
ready "$(port PS_PG_PORT 5542)" || missing+=(postgres)
ready "$(port PS_REDIS_PORT 5579)" || missing+=(redis)
ready "$(port PS_MOCK_AI_PORT 5550)" || missing+=(mockai)
((${#missing[@]})) || exit 0

"$ROOT/scripts/gen-local-env.sh" >/dev/null
echo "starting ${missing[*]}"
docker compose --env-file "$ENV_FILE" -f "$ROOT/deploy/compose/compose.yaml" \
  up -d --wait "${missing[@]}"
