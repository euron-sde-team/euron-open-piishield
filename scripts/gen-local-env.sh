#!/usr/bin/env bash
# Write deploy/compose/.env with random, local-only secrets (once; never overwrites).
# deploy/compose/.env.example documents every variable it may hold.
set -euo pipefail
f="$(cd "$(dirname "$0")/.." && pwd)/deploy/compose/.env"
if [[ -f "$f" ]]; then
  echo "deploy/compose/.env exists (delete it to regenerate)"
  exit 0
fi
rand() { openssl rand -base64 48 | tr -d '/+=\n' | cut -c1-"$1"; }
umask 077
# SESSION_SECRET, API_KEY_PEPPER and LOCAL_MASTER_KEY must all differ; the demo
# password is the published login of the seeded demo organisation (`make demo`), not a
# secret.
cat > "$f" <<ENV
SESSION_SECRET=$(rand 64)
API_KEY_PEPPER=$(rand 64)
LOCAL_MASTER_KEY=$(rand 64)
PIISHIELD_DEMO_PASSWORD=${PIISHIELD_DEMO_PASSWORD:-Demo-Owner-Pass-1}
ENV
echo "wrote deploy/compose/.env"
