# ADR-0002: The policy cache accepts bounded staleness instead of instant invalidation

- **Status:** Accepted
- **Date:** 2026-11-12

## Context

Every scan, protect, document and AI gateway call reads the calling project's policy
(required categories, masking method per category, confidence threshold) before it can do
anything. A naive implementation reads it from Postgres on every single call, which is a
query in the hot path of the product's single most frequent operation. The API runs as N
stateless replicas, so an in-process cache alone would let one replica serve a stale
policy indefinitely after an admin changes it on another.

A fully consistent alternative exists (a pub/sub invalidation channel: every admin write
publishes an event, every replica subscribes and evicts immediately), but it adds an
always-on subscription per replica, a channel to keep healthy, and a class of bug
("a replica missed the invalidation message") that a version-stamp read does not have.

## Decision

Cache the loaded `PolicySnapshot` in process memory, keyed by `project_id`, for up to
`policy_cache_ttl_s` (default 5 seconds). Every admin write bumps a per-project version
counter in the KV backend (`policies.service.bump`, `KV.incr`). A cache hit is only served
when **both** the local entry's age is under the TTL **and** its stored version still
matches the current value of that counter; a mismatch or an expired entry re-reads
Postgres and re-populates the cache. Every replica checks the version stamp on every
request regardless of its own cache state, which is cheap enough (one KV read) to do
unconditionally.

## Consequences

**Good**

- No subscription infrastructure, no channel to monitor, no missed-message failure mode.
  A replica's cache is self-healing on its very next request after a write, within the
  TTL ceiling.
- A single KV read per request is enough to detect staleness without re-fetching the whole
  policy from Postgres every time; the expensive read only happens on an actual miss.
- Correct even with no Redis at all: `MemoryKV`'s own version counter still invalidates a
  single-replica deployment's local cache immediately on write (there is only one process,
  so "every replica" is "this process").

**Bad / caveats**

- A policy change (for example, disabling masking for a category that acceptance
  criterion 10 would then refuse to protect unmasked) can take up to `policy_cache_ttl_s`
  to become visible on a replica that is not the one that made the change. This is a real,
  bounded staleness window, not instant invalidation, and it is documented in the module
  docstring, [HLD.md](../HLD.md)'s caching table, and [security.md](../security.md)
  rather than assumed away.
- This tradeoff is acceptable specifically because the values involved (a confidence
  threshold, a masking method, a required-categories list) are configuration, not a
  security gate that must take effect instantly (contrast: a kill switch or a budget hard
  limit in a different kind of product, where this design would not be appropriate).

## Alternatives considered

- **No caching, read Postgres on every call.** Rejected: unnecessary database load on the
  product's hottest path for data that changes rarely.
- **Pub/sub invalidation (Redis `PUBLISH`/`SUBSCRIBE`).** Rejected for 0.1.0: more moving
  parts (a live subscription per replica, reconnection handling) for a property (instant
  consistency) this product does not need for its own correctness guarantees.
- **A longer or unbounded TTL.** Rejected: 5 seconds was chosen as short enough that a
  policy change becomes effective within a time an operator would reasonably expect
  ("almost immediately") without eliminating the cache's benefit.
