# Euron Open PIIShield: developer entry points. `make` lists every target.
SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

COMPOSE_DIR := deploy/compose
FLOCI       := docker compose --env-file $(COMPOSE_DIR)/.env -f $(COMPOSE_DIR)/compose.yaml -f $(COMPOSE_DIR)/compose.floci.yaml
AWS_LOCAL   := docker compose --env-file $(COMPOSE_DIR)/.env -f $(COMPOSE_DIR)/compose.yaml -f $(COMPOSE_DIR)/compose.aws.yaml
API         := cd apps/api &&
WEB         := cd apps/web &&
TF_IMAGE    := hashicorp/terraform:1.16.6
TF_ENVS     := local-floci aws-dev aws-prod
# Use a local terraform when installed, otherwise the pinned container (providers cached
# in a named volume, so repeated runs do not download them again).
TF          := $(shell command -v terraform >/dev/null 2>&1 && echo terraform || echo docker run --rm -v $(CURDIR)/infra:/infra -v piishield-tf-plugins:/plugins -e TF_PLUGIN_CACHE_DIR=/plugins -w /infra/terraform $(TF_IMAGE))
TF_ROOT     := $(shell command -v terraform >/dev/null 2>&1 && echo infra/terraform || echo /infra/terraform)
ENV         ?= aws-dev
# Host ports, overridable in deploy/compose/.env (the same variables compose reads;
# defaults match docs/PLAN.md "Ports (project 15)").
envport      = $(or $(shell grep -s '^$(1)=' $(COMPOSE_DIR)/.env | cut -d= -f2),$(2))
WEB_PORT     = $(call envport,PS_WEB_PORT,5510)
API_PORT     = $(call envport,PS_API_PORT,5530)
PG_PORT      = $(call envport,PS_PG_PORT,5542)
MOCK_AI_PORT = $(call envport,PS_MOCK_AI_PORT,5550)
MAIL_PORT    = $(call envport,PS_MAILPIT_PORT,5525)
SMTP_PORT    = $(call envport,PS_SMTP_PORT,5526)
FLOCI_PORT   = $(call envport,PS_FLOCI_PORT,5566)
REDIS_PORT   = $(call envport,PS_REDIS_PORT,5579)
# The seeded demo login's password (published, not a secret); the seed, e2e and qa use
# it. Must match demo/seed.py's own DEMO_PASSWORD default, or `make demo` seeds one
# password while `make e2e`/`make qa` sign in with another.
DEMO_PW      = $(or $(shell grep -s '^PIISHIELD_DEMO_PASSWORD=' $(COMPOSE_DIR)/.env | cut -d= -f2),Demo-Owner-Pass-1)
# The integration suite's own databases and services on the Compose stack (never the app's).
TEST_ENV     = TEST_DATABASE_URL=postgresql+asyncpg://piishield:piishield@localhost:$(PG_PORT)/piishield_test \
               TEST_REDIS_URL=redis://localhost:$(REDIS_PORT)/15 \
               TEST_MOCKAI_URL=http://localhost:$(MOCK_AI_PORT) \
               TEST_SMTP_PORT=$(SMTP_PORT) TEST_MAILPIT_URL=http://localhost:$(MAIL_PORT) \
               TEST_AWS_ENDPOINT=http://localhost:$(FLOCI_PORT) TEST_KMS_KEY_ID=alias/piishield-local

.PHONY: help env up up-aws down logs ps demo admin backup restore test test-integration test-matrix \
        e2e qa screenshots bench lint typecheck build openapi sanitize \
        tf-fmt tf-validate tf-lint tf-security tf-aws-on-floci aws-deploy aws-migrate aws-admin aws-plan clean

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage: make \033[36m<target>\033[0m\n\n"} /^[a-zA-Z0-9_-]+:.*##/ { printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# --- Local ---------------------------------------------------------------------

env: ## Generate deploy/compose/.env with random local-only secrets
	@scripts/gen-local-env.sh

up: env ## Start everything on emulated AWS (Floci), provisioned by the same Terraform as production
	$(FLOCI) up -d --build --wait
	@echo ""
	@echo "  dashboard     http://localhost:$(WEB_PORT)"
	@echo "  api docs      http://localhost:$(API_PORT)/docs"
	@echo "  mail          http://localhost:$(MAIL_PORT)   (Mailpit)"
	@echo "  mock AI/LLM   http://localhost:$(MOCK_AI_PORT)"
	@echo ""
	@echo "  Next: make demo   (a seeded organisation: projects, policies, scans, findings, vault entries)"

up-aws: env ## Start the stack against real AWS resources (needs deploy/compose/.env.aws)
	@test -f $(COMPOSE_DIR)/.env.aws || { echo "copy $(COMPOSE_DIR)/.env.aws.example to .env.aws first"; exit 1; }
	$(AWS_LOCAL) up -d --build --wait

demo: ## Seed the demo organisation and print the logins
	$(FLOCI) exec -T api piishield seed-demo
	@echo ""
	@echo "  Sign in at http://localhost:$(WEB_PORT) with a login above"

admin: ## Create an organisation and its owner, or reset an owner (EMAIL=you@example.com; prompts for the password)
	@test -n "$(EMAIL)" || { echo "usage: make admin EMAIL=you@example.com [ORG='My Company']"; exit 1; }
	$(FLOCI) exec api piishield create-admin --email "$(EMAIL)" --org "$(or $(ORG),My Company)"

backup: ## Back up the local stack: Postgres dump and the exports bucket, into backups/
	@scripts/backup.sh

restore: ## Restore a backup into the running stack (BACKUP=backups/<timestamp>)
	@test -n "$(BACKUP)" || { echo "usage: make restore BACKUP=backups/<timestamp>"; exit 1; }
	@scripts/restore.sh "$(BACKUP)"

down: ## Stop the stack and delete its data (the Terraform provider cache survives)
	-$(FLOCI) down --remove-orphans
	-docker volume rm piishield_pgdata piishield_redisdata piishield_exports piishield_flocidata piishield_tfdata 2>/dev/null
	-$(AWS_LOCAL) down --remove-orphans 2>/dev/null

logs: ## Tail logs (SERVICE=api|web|mockai|migrate|tf-local-floci|floci|mailpit)
	$(FLOCI) logs -f --tail 100 $(SERVICE)

ps: ## Show stack status
	$(FLOCI) ps

# --- Quality ---------------------------------------------------------------------

lint: ## Lint the API (ruff) and the web app (eslint)
	$(API) uv run ruff check src tests && uv run ruff format --check src tests
	$(WEB) pnpm lint

typecheck: ## Typecheck the API (mypy --strict) and the web app (tsc)
	$(API) uv run mypy --strict src tests
	$(WEB) pnpm typecheck

test: ## Unit tests: API (pytest) and web (vitest). No database, no network
	$(API) uv run pytest tests/unit -q
	$(WEB) pnpm test

test-integration: ## API integration tests against the Compose Postgres, Redis, mock AI/LLM and Floci (started if needed)
	@scripts/test-db.sh
	$(API) $(TEST_ENV) uv run pytest tests/integration -m integration -q --cov --cov-report=term-missing:skip-covered

test-matrix: ## Integration tests under every backend: storage/keys local|S3+KMS via Floci
	@scripts/test-matrix.sh

e2e: ## Browser end-to-end tests (Playwright) against the running stack (make up && make demo)
	cd e2e && pnpm install --frozen-lockfile && pnpm exec playwright install chromium && \
	  WEB_URL=http://localhost:$(WEB_PORT) API_URL=http://localhost:$(API_PORT) MAILPIT_URL=http://localhost:$(MAIL_PORT) \
	  PIISHIELD_DEMO_PASSWORD='$(DEMO_PW)' E2E_PASSWORD='$(DEMO_PW)' pnpm test

qa: ## Browser QA sweep (Puppeteer): every page, light and dark, desktop and phone
	cd scripts/qa && pnpm install --frozen-lockfile && \
	  QA_BASE=http://localhost:$(WEB_PORT) QA_MAILPIT=http://localhost:$(MAIL_PORT) \
	  PIISHIELD_DEMO_PASSWORD='$(DEMO_PW)' QA_PASSWORD='$(DEMO_PW)' node qa.mjs

screenshots: ## Curated screenshots (docs/assets/screenshots) and the tour GIF, from the seeded stack
	cd scripts/qa && pnpm install --frozen-lockfile && \
	  QA_BASE=http://localhost:$(WEB_PORT) QA_MAILPIT=http://localhost:$(MAIL_PORT) \
	  PIISHIELD_DEMO_PASSWORD='$(DEMO_PW)' QA_PASSWORD='$(DEMO_PW)' node screenshots.mjs && ./make-tour.sh

bench: ## Benchmarks (scan/mask/tokenize throughput and latency, vault lookup, rollup computation) into docs/bench.json
	@scripts/test-db.sh
	$(API) uv run python bench.py --database-url postgresql+asyncpg://piishield:piishield@localhost:$(PG_PORT)/piishield_test \
	  --redis-url redis://localhost:$(REDIS_PORT)/14 --out ../../docs/bench.json

build: ## Build the container images (server, web)
	$(FLOCI) build

openapi: ## Regenerate docs/api/openapi.yaml from the FastAPI app
	@mkdir -p docs/api
	$(API) uv run piishield openapi > ../../docs/api/openapi.yaml

sanitize: ## Scan committable files for credentials, cloud identifiers and em/en dashes
	@scripts/check-sanitization.sh

# --- Terraform ---------------------------------------------------------------------

tf-fmt: ## Format all Terraform
	$(TF) fmt -recursive $(TF_ROOT)

tf-validate: ## terraform validate every environment (no backend, no credentials)
	@for env in $(TF_ENVS); do \
	  echo "== $$env"; \
	  $(TF) -chdir=$(TF_ROOT)/envs/$$env init -backend=false -input=false -no-color >/dev/null && \
	  $(TF) -chdir=$(TF_ROOT)/envs/$$env validate -no-color || exit 1; \
	done

tf-lint: ## tflint every module and environment (plugins cached in a docker volume)
	docker run --rm -v $(CURDIR)/infra:/infra -v piishield-tflint:/plugins -e TFLINT_PLUGIN_DIR=/plugins -w /infra/terraform ghcr.io/terraform-linters/tflint:v0.64.0 --init
	docker run --rm -v $(CURDIR)/infra:/infra -v piishield-tflint:/plugins -e TFLINT_PLUGIN_DIR=/plugins -w /infra/terraform ghcr.io/terraform-linters/tflint:v0.64.0 --recursive --format compact

tf-security: ## checkov policy scan of the Terraform (any unskipped finding fails; every skip carries its reason inline)
	docker run --rm -v $(CURDIR)/infra:/infra -w /infra/terraform bridgecrew/checkov:3.3.30 -d . --config-file .checkov.yaml

tf-aws-on-floci: ## Plan, apply, re-plan and destroy the full aws-dev environment against a throwaway Floci (port 5596)
	@scripts/tf-aws-on-floci.sh

aws-deploy: ## One shot, migrate first: registries, images, infrastructure, migrations, rollout (ENV=aws-dev|aws-prod TAG=...)
	@test -n "$(TAG)" || { echo "usage: make aws-deploy ENV=aws-dev TAG=0.1.0"; exit 1; }
	@scripts/aws-deploy.sh $(ENV) $(TAG)

aws-migrate: ## Run database migrations as a one-off ECS task (ENV=...)
	@scripts/aws-run-task.sh $(ENV) migrate

aws-admin: ## Create the first owner as a one-off ECS task (ENV=... EMAIL=...; PIISHIELD_ADMIN_PASSWORD in your env)
	@test -n "$(EMAIL)" || { echo "usage: PIISHIELD_ADMIN_PASSWORD=... make aws-admin ENV=aws-dev EMAIL=you@example.com [ORG='Acme']"; exit 1; }
	@test -n "$$PIISHIELD_ADMIN_PASSWORD" || { echo "set PIISHIELD_ADMIN_PASSWORD (at least 10 characters, upper and lower case and a digit)"; exit 1; }
	@scripts/aws-run-task.sh $(ENV) create-admin --email "$(EMAIL)" --org "$(or $(ORG),My Company)"

aws-plan: ## terraform plan for ENV (aws-dev | aws-prod); needs terraform.tfvars and AWS credentials
	cd infra/terraform/envs/$(ENV) && terraform init -input=false && terraform plan

clean: ## Remove build output and caches
	rm -rf apps/web/.next apps/api/.pytest_cache apps/api/.mypy_cache apps/api/.ruff_cache apps/api/.coverage \
	  e2e/test-results e2e/playwright-report scripts/qa/output reports
