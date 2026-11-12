# Local with AWS (Floci)

`make up` starts PIIShield against **Floci**, a local AWS emulator, provisioned by the
exact same Terraform modules that build real AWS (`infra/terraform/modules/`), applied
against the emulator by a one-shot `tf-local-floci` container before the API and
migration containers start. This proves the IaC plans, applies and runs cleanly on every
local run, not just in CI.

## What Floci actually emulates here

`deploy/compose/compose.floci.yaml` provisions, through `infra/terraform/envs/local-floci`:

- A KMS key and alias (`alias/piishield-local`).
- An S3 exports bucket.
- Secrets Manager secrets.
- An SES identity.

## What 0.1.0's app code actually calls

This is the important distinction: **the Terraform proves the infrastructure is correct;
it does not mean the application uses all of it yet.** Per `compose.floci.yaml`'s own
comment and `core/config.py`'s "accepted but unused" fields:

| Resource Terraform provisions on Floci | 0.1.0 app behavior |
| --- | --- |
| KMS key/alias | `KEY_MODE` stays `local` even under the Floci overlay. The key exists for `make tf-aws-on-floci` and a future KMS-backed `Sealer` to target; nothing in 0.1.0 reads it yet. |
| S3 exports bucket | Unused. Document protection is request-scoped (`STORAGE=local` behavior regardless of the `STORAGE` setting), see [configuration.md](configuration.md). |
| Secrets Manager secrets | Unused by the app (`AWS_SECRETS_ENABLED` has no read path yet); secrets are read from the container's environment. |
| SES identity | **Used**, conditionally. `MAIL_BACKEND` defaults to `smtp` under the Floci overlay (Mailpit at `http://localhost:5525`), so a fresh `make up` shows review-queue and scan-report mail without first verifying a sender identity and, in the SES sandbox, every recipient. Set `PS_MAIL_BACKEND=ses` in `deploy/compose/.env` to route through the real SES identity Terraform created on Floci instead; mail then lands in Floci's SES, not Mailpit. |

This asymmetry is deliberate: the overlay's own comment says plainly that it "must not
turn on env values the app cannot serve." Running the Terraform against Floci on every
`make up` is what proves the infrastructure definitions are correct ahead of a real AWS
deployment, independent of how much of it the application currently calls.

## Running it

```sh
make env
make up
```

Logs for the one-shot Terraform apply:

```sh
make logs SERVICE=tf-local-floci
```

Floci's own edge is reachable at `http://localhost:5566` if you want to inspect what was
created directly (for example with the AWS CLI against `--endpoint-url
http://localhost:5566`, region `us-east-1`, any placeholder credentials).

## Exercising the real SES path

```sh
# deploy/compose/.env
PS_MAIL_BACKEND=ses
```

Then `make up` again (or restart the `api` service) and verify a recipient identity
against Floci's emulated SES the way you would against the sandbox for real AWS SES, per
Floci's own documentation. Mail sent this way will not appear in Mailpit.

## Proving the infrastructure end to end

```sh
make tf-aws-on-floci
```

A separate, heavier check from `make up`'s own one-shot apply: this plans, applies,
re-plans (asserting zero adds or replacements) and destroys the full `aws-dev` environment
(173 resources on the most recent run) against a second, throwaway Floci instance on its
own port (5596), independent of whatever `make up` currently has running. See
[deploy-aws.md](deploy-aws.md) and [testing.md](testing.md).
