# ADR-0001: Envelope encryption for the vault, local key backend only in 0.1.0

- **Status:** Accepted
- **Date:** 2026-11-12

## Context

The vault (`vault_entries`) is the only place an original value can ever be recovered
from a tokenized placeholder. Whatever encrypts it needs to survive a master-key rotation
without re-encrypting every row, and needs to make a ciphertext copied between rows
useless, since `value_fingerprint` collisions or a restored backup could otherwise put one
row's encrypted bytes where another's belong.

0.1.0 also needs to ship without requiring an operator to stand up AWS KMS (or an
emulator of it) just to run a demo locally. The program's standing rule is that every
local resource has a real Terraform-provisioned AWS equivalent, but that does not mean
0.1.0's app code must call every one of those resources on day one.

## Decision

Encrypt every vault entry with envelope encryption: a fresh, random 256-bit AES-GCM key
per record, generated implicitly by AES-GCM's own nonce and key material rather than a
separately wrapped data key, with the ciphertext bound to that specific row by AEAD
associated data (`vault:<entry_id>`). Key management sits behind a `Sealer` Protocol with
exactly `seal(plaintext, context)` and `open(sealed, context)`.

0.1.0 ships one implementation, `LocalSealer`: the AES key is derived from
`sha256(LOCAL_MASTER_KEY)`, an operator-supplied environment value. `build_sealer` raises
`NotImplementedError` for `key_mode=kms` rather than falling back to the local backend
silently. A deployment that configures `KEY_MODE=kms` without a working implementation
must fail at boot, not serve traffic with weaker protection than it asked for.

## Consequences

**Good**

- Rotating `LOCAL_MASTER_KEY` only requires re-sealing existing rows under the new key
  (a migration task), never a surprise that the key itself is embedded in old ciphertexts
  in a way rotation cannot fix.
- The AEAD context binding means a vault row's ciphertext is useless outside that row:
  copying `sealed_value` from one entry to another (accidentally, or by an attacker with
  write access to the table but not the key) produces a blob that fails to decrypt.
- The `Sealer` Protocol is the only seam a future KMS backend needs: a `KmsSealer`
  implementing the same two methods drops in behind `build_sealer`'s existing `key_mode`
  switch, with no call site in `vault/service.py` or elsewhere needing to change.
- A local deployment runs with no dependency on AWS KMS or an emulator of it.

**Bad / caveats**

- `key_mode=local` means the master key's security is only as good as the environment or
  secret store it comes from; there is no hardware-backed key isolation, and no separate
  key administrator role distinct from whoever can read the deployment's environment.
- An operator who needs KMS-backed key isolation (a real compliance requirement for some
  organizations) cannot get it from 0.1.0; `key_mode=kms` is a hard failure, not a
  degraded fallback. This is the correct behavior (fail loud, not silent), but it does
  mean KMS support is a release blocker for that operator, not a configuration toggle.
- Key rotation itself (re-sealing every existing row under a new master key) is not an
  automated 0.1.0 feature; it would be a manual migration today.

## Alternatives considered

- **A single master key encrypting every row directly** (no per-row data key or context
  binding). Rejected: rotating the master key would mean re-encrypting every row in one
  operation, and a ciphertext copied between rows would open successfully, silently
  revealing the wrong value under the wrong placeholder.
- **Shipping a `KmsSealer` in 0.1.0 alongside `LocalSealer`.** Rejected for this release:
  it adds an AWS dependency (even against Floci) to the smallest possible local demo path,
  for a feature (reversible tokenization) that already works correctly and safely under
  `key_mode=local`. Deferred to the roadmap behind the same `Sealer` Protocol.
- **Falling back to `local` when `kms` is requested but unavailable.** Rejected: this
  would let a misconfigured production deployment silently run with a weaker key backend
  than it believed it had configured. `build_sealer` fails loudly instead.
