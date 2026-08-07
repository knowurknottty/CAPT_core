# CAPT Core Roadmap

This roadmap separates **released**, **next**, and **future** work. Historical milestones are preserved without being mislabeled as the current release.

## Current release: v0.5

Released and evidenced:

- [x] CAPT Solo local Memory Engine with provenance, confidence, metadata, import/export, backup, and integrity checks.
- [x] CTP operational transaction journal with receipts, idempotency, correlation IDs, and recovery state.
- [x] KHSB in-process coordination.
- [x] Proof Engine, Capability Registry, ClaimGuard, Skill Foundry, Workflow Proof, and Knowledge Bubble lifecycle controls.
- [x] EventStore authoritative runtime event ledger with ordered persistence and replay.
- [x] Authenticated standalone harness service.
- [x] TaskResolver and DriverHost composition.
- [x] Checkpoint, restart, and no-repeat resume behavior.
- [x] Runtime Memory Governor, ContextPack construction, rotation, stale-pack rejection, and budget enforcement.
- [x] Packaged Hermes and OpenHarness driver surfaces.
- [x] Bounded read-only Hermes operator action proven locally through an installed wheel.
- [x] Python 3.10 and 3.12 hosted CI for build, install, import, package inspection, contracts, regression tests, secrets, and dependency audit.
- [x] Versioned release evidence under `release_evidence/v0.5`.

Explicit boundaries:

- General unrestricted model-driven repository engineering is not proven.
- KHSB is not durable or cross-process.
- CTP is not the authoritative EventStore ledger.
- The CAPT Solo Memory Engine and Runtime Memory Governor are distinct.
- Hosted CI does not rerun the external Hermes/provider lifecycle.
- Hosted security status is degraded when the private optional anti-token-extraction dependency cannot be verified.

## Near-term hardening

- [ ] Modernize package license metadata and raise the setuptools floor deliberately.
- [ ] Restore a meaningful scoped or changed-line coverage policy.
- [ ] Review PR #28 history and port only still-relevant adversarial OpenHarness tests to the canonical DriverHost implementation.
- [ ] Rewrite the external Hermes compatibility skill against the v0.5 `capt harness` command surface.
- [ ] Independently validate the rewritten Hermes compatibility package before moving it from Treasure Chest to a dedicated repository.
- [ ] Add a documented private vulnerability-reporting channel.
- [ ] Add a concise post-merge release attestation linking runtime source, evidence, wheel, and merge identities.

## Runtime usability

- [ ] Improve installed CLI discoverability and examples for harness commands.
- [ ] Complete a polished operator-facing TUI or desktop workflow without moving authority out of RuntimeService.
- [ ] Add model-adapter configuration guides for local-first runtimes.
- [ ] Expand bounded operator actions only with explicit capability, lease, verification, and adversarial tests.

## Security and trust

- [ ] Optional encrypted backup and export.
- [ ] Cryptographically signed release attestations and receipts.
- [ ] Cryptographic Knowledge Bubble signature verification.
- [ ] Stronger process isolation for optional external drivers.
- [ ] Multi-user identity and authorization as a separate higher-trust profile.

## Memory and context

- [ ] Additional retrieval adapters behind the existing memory boundary.
- [ ] Cross-model continuity demonstrations using the same authoritative runtime state.
- [ ] Better ContextPack observability and operator diagnostics.
- [ ] Policy-driven retention, consolidation, and archival controls.

## Future architecture

These are directions, not implementation claims:

- distributed or cross-process KHSB transports;
- alternate durable storage backends;
- multi-agent federation;
- additional audio, vision, and multimodal drivers;
- remote stores behind authenticated interfaces;
- signed and independently verifiable audit chains.

## Historical milestones

Earlier versions established the CAPT Solo Memory Engine, CTP, KHSB, Foundry, proof, ClaimGuard, Knowledge Bubbles, migration safeguards, and optional anti-token-extraction integration. Their exact historical test and tool counts are retained in release history and evidence documents, not treated as current v0.5 status.

## Versioning policy

- **Major:** breaking changes to supported public API or runtime contracts.
- **Minor:** additive capabilities or supported integration surfaces.
- **Patch:** fixes and documentation changes that preserve public contracts.

A roadmap checkbox is not release evidence. A capability becomes a public release claim only after implementation, tests, preserved evidence, and documentation agree.
