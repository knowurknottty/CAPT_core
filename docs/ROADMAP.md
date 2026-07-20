# CAPT Solo v0.1 — Roadmap

This is the **smallest stable public foundation**. The items below are reserved
extension points — they are NOT in v0.1 and have no code behind them yet.

## v0.1 (this release) — DONE

- [x] Local-first Memory Engine (SQLite) with tags, namespaces, provenance,
      confidence, metadata, export/import, backup.
- [x] CTP append-only transaction journal with receipts, idempotency, correlation
      ids, audit trail, and crash recovery.
- [x] KHSB in-process message bus (publish/subscribe/request/reply/timeout/ack).
- [x] Hermes plugin with 10 stable public tools.
- [x] 8 beginner-friendly skills.
- [x] One-command install / doctor / uninstall / verify.
- [x] Production docs (9 files).
- [x] Automated tests, 95%+ public-surface coverage.
- [x] Versioned schema with migration hook.

## v0.2 (candidates)

- [ ] Vector search adapter reference implementation (pluggable, opt-in).
- [ ] `capt_health` richer report (per-subsystem latency, counts).
- [ ] Backup rotation / retention policy.
- [ ] Encrypted export/backup (`--encrypt`).

## v0.3 (candidates)

- [ ] Distributed KHSB transport (networking behind a config flag, off by default).
- [ ] Remote memory store backend (same public API).
- [ ] GPG-signed CTP receipts.

## v0.4 (this release) — DONE

- [x] Skill Foundry (procedure → skill → 12-stage validate → review → publish).
- [x] Proof Engine (evidence + aggregation).
- [x] Capability Registry (candidate→validated→proven→verified; 12 degradation codes).
- [x] ClaimGuard (claim validation + scoped degradation language).
- [x] Knowledge Bubble Runtime (v2 manifest, 12-step validation, quarantine-default).
- [x] Governance Layer (CTP-bounded, audited).
- [x] Workflow Proof Engine (composed workflows carry independent proof).
- [x] Migration safety gate (backup-gated, abort on failure).
- [x] CLI `foundry` group + 10 new plugin tools (46 total).
- [x] Doctor/verify extensions + boundary audit.
- [x] 348 tests passing; verify_runtime 5/5 sections.

## v0.4.1 (this release) — DONE

- [x] Anti-Token-Extraction component (optional, independently degradable).
- [x] Local child-process stdio only; cache mode off; sensitive-input refusal.
- [x] Pinned upstream repo + commit recorded in component manifest.
- [x] Legacy cache purge on bootstrap/upgrade.
- [x] Hermes MCP template (stdio, no creds, isolation metadata).
- [x] Capability registry + installer + doctor + verify_runtime + docs updated.
- [x] 9 required integration tests; all 17 v0.4 release gates remain green.
- [x] Plugin tool `capt_anti_token_extraction_status` (47 total).

## v1.0 (candidates)

- [ ] Multi-agent federation via CTP correlation ids.
- [ ] bioCAPT integration as a local memory consumer.
- [ ] Web UI for memory browsing (local-only, no network).
- [ ] Signed bubble verification (signature_metadata is placeholder in v0.4).
- [ ] Automated re-verification on environment change.

## Non-goals (explicitly out of scope)

- Cloud sync / multi-device live replication.
- Hosting CAPT Solo as a service for untrusted users.
- Replacing the full CAPT architecture — Solo is a foundation, not the whole.

## Versioning policy

- **Major:** breaking change to a public signature in `capt_solo.api` or a
  plugin tool.
- **Minor:** additive (new tool, new optional param, new extension point).
- **Patch:** bug fix / doc / internal change with no public-surface change.
