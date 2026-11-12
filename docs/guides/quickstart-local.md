# Quickstart (local)

This gets you a running PIIShield stack, a seeded demo organisation, and your first
protected scan, with no AWS account and no host dependency beyond Docker. This is the
proof behind acceptance criterion 1: a fresh API key can scan a text sample for PII within
minutes of these steps, with no other configuration.

## Prerequisites

- Docker and Docker Compose.
- `curl` (or any HTTP client) to try the API directly.
- Nothing else. Postgres, Redis, the AWS emulator (Floci), the mock AI service, the API
  and the dashboard all run as Compose services.

## 1. Generate local secrets

```sh
make env
```

Writes `deploy/compose/.env` (gitignored) with random values for `SESSION_SECRET`,
`API_KEY_PEPPER` and `LOCAL_MASTER_KEY`, plus the published demo password
`PIISHIELD_DEMO_PASSWORD=Demo-Owner-Pass-1`. Safe to re-run; it will not overwrite an
existing file with different secrets your running stack already depends on.

## 2. Start the stack

```sh
make up
```

Brings up Postgres, Redis, Floci (the local AWS emulator), a one-shot Terraform apply
against Floci, the mock AI service, the API and the web dashboard, waiting until every
service reports healthy. On success you will see:

```
  dashboard     http://localhost:5510
  api docs      http://localhost:5530/docs
  mail          http://localhost:5525   (Mailpit)
  mock AI/LLM   http://localhost:5550
```

| Service | Local port |
| --- | --- |
| web (dashboard) | 5510 |
| api | 5530 |
| postgres | 5542 |
| redis | 5579 |
| floci (AWS emulator) | 5566 |
| mailpit | 5525 |
| mock AI | 5550 |

## 3. Seed the demo organisation

```sh
make demo
```

Runs `piishield seed-demo` inside the `api` container: a realistic organisation (projects,
policies, sample scans, findings across every category, vault entries, review items) so
the dashboard looks alive from the first sign-in, and prints the seeded logins. The owner
login used throughout this documentation is:

```
email:    priya.nair@verdantpay.example
password: Demo-Owner-Pass-1
```

Sign in at [http://localhost:5510](http://localhost:5510).

## 4. Create a project API key

From the dashboard: **API Keys** in the left nav, under ORGANISATION, then create a key
with `write` scope for the seeded project. The full key (`pii_<prefix>_<secret>`) is shown
once, at creation; copy it now.

Or from the CLI, inside the API container:

```sh
docker compose --env-file deploy/compose/.env -f deploy/compose/compose.yaml \
  -f deploy/compose/compose.floci.yaml exec api piishield create-admin \
  --email you@example.com --org "My Company"
```

(`create-admin` creates an organisation and its owner if you want a second one instead of
using the seeded demo; API keys themselves are created from the dashboard or
`POST /api/v1/auth/keys` once signed in.)

## 5. Scan your first piece of text

With a project API key in hand (`pii_<prefix>_<secret>`):

```sh
curl -s http://localhost:5530/api/v1/detectors/scan \
  -H "Authorization: Bearer pii_<prefix>_<secret>" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "<your-project-id>",
    "text": "Contact Priya Nair at priya.nair@verdantpay.example or 98765 43210. Card 4111111111111111, PAN ABCPD1234E."
  }'
```

This is the dedicated, side-effect-free detection route: it reports findings and writes
no audit entry, unlike `protect`. The response lists one finding per detected value, each
with its `category` (one of `contact`, `credential`, `financial`, `government_id`,
`personal`), the exact `start`/`end` character offsets, a `confidence` score, whether its
checksum passed (`checksum_valid`), and the specific `recognizer` that matched (`email`,
`phone_in`, `credit_card`, `pan`, and so on). A 10-digit string that fails its checksum is
correctly never reported at all, see [docs/architecture/LLD.md](../architecture/LLD.md).

## 6. Protect it

```sh
curl -s http://localhost:5530/api/v1/protect/text \
  -H "Authorization: Bearer pii_<prefix>_<secret>" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "<your-project-id>",
    "text": "Contact Priya Nair at priya.nair@verdantpay.example or 98765 43210."
  }'
```

Returns the protected text (per the project's policy, default: tokenize everything), the
finding list with the method applied to each, and a `scope_id` you can reuse so the same
value tokenizes to the same placeholder again (acceptance criterion 4). See
[configuration.md](configuration.md) for setting a project's policy, and
[walkthrough.md](walkthrough.md) for the same flow through the dashboard.

## Next steps

- [configuration.md](configuration.md): every environment variable and what it controls.
- [walkthrough.md](walkthrough.md): a full tour of the dashboard, including the Token
  Vault, the Review Queue and the AI Gateway.
- [testing.md](testing.md): running the test suites yourself.
- `make down` stops the stack and deletes its local data (Postgres, Redis, Floci volumes).
