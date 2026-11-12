#!/usr/bin/env bash
# Run the API integration suite under every backend combination PIIShield's own code
# actually branches on in 0.1.0:
#
#   cache/KV: Redis | in-process memory (core/kv.py's create_kv: an empty redis_url
#             falls back to MemoryKV, used for the policy cache and tokenize scope map)
#
# 2 runs. An earlier version of this script ran a "storage=s3, KEY_MODE=kms" leg, but
# 0.1.0 has no S3 storage backend and sealing.py deliberately raises NotImplementedError
# for key_mode=kms (see core/sealing.py's own ADR-style comment); that leg could only
# ever fail, on every test, for a reason unrelated to the code under test. Each
# combination gets its own test database, so a run never reuses another's state.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/deploy/compose/.env"
port() { local v; v="$(grep -s "^$1=" "$ENV_FILE" | cut -d= -f2 || true)"; echo "${v:-$2}"; }
PG="postgresql+asyncpg://piishield:piishield@localhost:$(port PS_PG_PORT 5542)"
REDIS="redis://localhost:$(port PS_REDIS_PORT 5579)/14"

"$ROOT/scripts/test-db.sh"

export TEST_MOCKAI_URL="http://localhost:$(port PS_MOCK_AI_PORT 5550)"
# Docker is the only host prerequisite (no host psql assumed): create each matrix
# database through the already-running postgres container itself.
PG_CONTAINER="$(cd "$ROOT" && docker compose --env-file "$ENV_FILE" -f deploy/compose/compose.yaml ps -q postgres)"
failed=()
runs=0
for kv in redis memory; do
  runs=$((runs + 1))
  echo
  echo "== kv=$kv"
  db="piishield_test_matrix_${kv}"
  docker exec -e PGPASSWORD=piishield "$PG_CONTAINER" \
    psql -U piishield -d piishield -v ON_ERROR_STOP=1 \
    -c "DROP DATABASE IF EXISTS ${db};" -c "CREATE DATABASE ${db};" >/dev/null
  redis_url=""; [[ "$kv" == redis ]] && redis_url="$REDIS"
  if ! (cd "$ROOT/apps/api" && TEST_REDIS_URL="$redis_url" \
        TEST_DATABASE_URL="$PG/${db}" \
        uv run pytest tests/integration -m integration -q -p no:warnings -rf); then
    failed+=("kv=$kv")
  fi
done
echo
if ((${#failed[@]})); then
  printf 'matrix: FAILED for %s\n' "${failed[@]}"
  exit 1
fi
echo "matrix: all $runs combinations passed"
