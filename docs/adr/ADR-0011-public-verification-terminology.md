# ADR-0011 — Public Verification Record Terminology

- **Status:** Accepted
- **Date:** 2026-07-29
- **Supersedes:** none
- **Related:** ADR-0002, ADR-0006, ADR-0009

## Context

CAPT uses “verify,” “proof,” “evidence,” and “receipt” in several subsystem-
specific ways. Public integrations need precise terms even though v0.5 retains
the existing classes.

## Decision

- **check** — one observation-producing verifier execution;
- **evidence** — an observation plus its provenance;
- **evaluation** — application of a policy to evidence for a subject state;
- **attestation** — a portable result of an evaluation;
- **receipt** — an integrity-bound record that an operation, evaluation, or
  governed decision occurred.

“Proof” may remain product and subsystem language for an evidence aggregate. It
does not imply mathematical certainty unless the underlying verifier establishes
that property.

These definitions govern new public documentation and interfaces. They do not
force all v0.5 internal classes into one implementation.

## Evidence

The definitions separate the actual stages currently distributed across VSI,
Evidence, Foundry, ContextPack validation, Governance, and CTP.

## Consequences

- Public claims can distinguish observations from policy judgments.
- Existing class names and persisted formats remain compatible.
- Future record convergence has a stable vocabulary.

## Alternatives Considered

- Preserving overloaded terminology was rejected because it makes portable
  verification ambiguous.

## Related Invariants

I-02, I-04, I-08, I-12, I-15.
