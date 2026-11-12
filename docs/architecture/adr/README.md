# Architecture Decision Records

Each ADR captures one significant decision: the context that forced it, what we chose,
and what it costs us. ADRs are immutable once accepted. To revisit one, write a new ADR
that supersedes it.

| ADR | Decision | Status |
| --- | --- | --- |
| [0001](0001-envelope-encryption-local-key-only.md) | Envelope-encrypt every vault entry (AES-256-GCM, per-row context binding); ship only the local key backend in 0.1.0, KMS is roadmap behind the same Sealer protocol | Accepted |
| [0002](0002-bounded-staleness-policy-cache.md) | The project policy cache accepts a bounded staleness window (5s TTL plus a version stamp) instead of pub/sub invalidation | Accepted |
| [0003](0003-fixed-priority-overlap-resolution.md) | Recognizer overlap resolution is fixed-priority, first-claim-wins by list order, most specific and checksum-validated first | Accepted |

**Template:** Status / Date, then Context, Decision, Consequences (good and bad), and
Alternatives considered.
