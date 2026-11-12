# ADR-0003: Fixed-priority, first-claim-wins overlap resolution between recognizers

- **Status:** Accepted
- **Date:** 2026-11-12

## Context

Several recognizers can match overlapping spans of the same text. A 16-digit run of
digits looks like both a candidate credit card number and a candidate generic bank
account number. A 10-digit Indian mobile number can also look like a truncated match for
a less specific digit pattern. Without some rule for which recognizer "owns" a span, the
same substring could be reported twice, once correctly (as a checksum-validated card) and
once incorrectly (as an unvalidated bank account), which would both double-count the
finding and weaken the product's core promise that a checksum-invalid value is never
reported as that category (acceptance criterion 2: a 10-digit non-PII number must never
be flagged as a card or Aadhaar number by checksum, and a true positive must not also be
drowned in a redundant low-confidence duplicate).

## Decision

`detectors/recognizers.py`'s `RECOGNIZERS` table is an ordered list, most specific and
highest-signal first (`jwt`, `api_key`, `password_assignment`, `credit_card`, `iban`,
`swift_bic`, `ifsc`, `email`, `upi_id`, `aadhaar`, `pan`, `us_ssn`, `passport`,
`driving_licence`, `phone_in`, `phone_us`, the unvalidated `bank_account`, then
`date_of_birth`, `address`, `person_name`). `scan_text` walks the list in this order and
tracks every span already claimed; a later recognizer's match is dropped if it overlaps
any already-claimed span, regardless of that later recognizer's own confidence or whether
its own checksum would have passed. `email` is deliberately ordered before `upi_id` for
the same reason: an email address's domain has a dot before its final label, while a UPI
handle's bank suffix does not, so checking email first and excluding a trailing dot from
`upi_id`'s pattern keeps the two recognizers from fighting over the same `@`-containing
string. `bank_account` (no checksum, a pure 9 to 18 digit count match) is placed last among
every digit-shaped recognizer specifically so a valid Aadhaar, PAN-adjacent, SSN or phone
number is claimed by its correct, validated recognizer before the generic digit-count
match ever gets a chance to steal that span.

## Consequences

**Good**

- A single real value produces exactly one finding, from the most specific recognizer that
  matches it, with that recognizer's own checksum result attached (a valid 16-digit card
  number is reported once, as `credit_card`, `checksum_valid=true`, never a second time as
  an unvalidated `bank_account`).
- The algorithm is simple, deterministic, and easy to reason about: the table's order is
  the entire policy, with each entry's placement commented inline where the reasoning is
  not obvious from confidence alone (see the `bank_account` and `email`/`upi_id` comments
  in `recognizers.py`).
- Adding a new recognizer is a matter of choosing where in the list it belongs, not writing
  new conflict-resolution logic.

**Bad / caveats**

- Ordering is a manually maintained property of the list, not something the type system or
  a test enforces structurally; a future contributor who inserts a new, low-specificity
  recognizer too early in the list could silently steal spans from more specific
  recognizers later in it. The existing unit tests (one per recognizer family, checksum
  valid vs invalid) catch the symptom (a known-good value no longer gets the right
  category) but a reviewer still has to understand the ordering rule to review a change
  to it correctly.
- "First claim wins" means a genuinely ambiguous string (one that could legitimately be
  two different kinds of PII) always resolves to whichever recognizer is listed first, with
  no mechanism to report both findings or to prefer the higher-confidence one when order
  and confidence disagree. In practice this has not come up for the recognizer set in
  0.1.0, because the ordering was chosen to put every checksum-validated recognizer ahead
  of every unvalidated one.

## Alternatives considered

- **Report every match, including overlaps.** Rejected: double-reports the same substring
  under two categories, which complicates every downstream consumer (policy decisions,
  the review queue, the audit log's category counts) for no benefit.
- **Resolve overlaps by highest confidence rather than list order.** Rejected: confidence
  scores are tuned per recognizer for a different purpose (the review-queue threshold,
  acceptance criterion 13) and conflating them with overlap priority would make both
  harder to tune independently. A checksum-validated `credit_card` match (confidence 0.95)
  already naturally outranks an unvalidated `bank_account` match (confidence 0.3) under
  this scheme anyway, so list order and confidence point the same direction for the cases
  that matter in 0.1.0's recognizer set.
