# CAPT Solo v0.1

Local-first cognitive runtime for individual developers, integrating natively
with Hermes. Zero cloud, zero external database, zero Docker, zero network.

## Quick start

```bash
git clone <repo> capt-solo && cd capt-solo
./install.sh        # detect Hermes, install plugin + skills, init runtime
./verify.sh         # one-command health check (memory + CTP + KHSB)
```

## What you get

- **Memory Engine** — SQLite store with tags, namespaces, provenance, confidence,
  metadata, semantic-search adapter interface, export/import, backups.
- **CTP Runtime** — append-only transaction journals with receipts, idempotency,
  correlation ids, audit trail, and crash recovery.
- **KHSB** — in-process message bus (publish/subscribe/request/reply/timeout/ack).
- **Hermes Plugin** — 10 stable public tools (`capt_store_memory`, etc.).
- **8 Skills** — bootstrap, debug, arch-decision, memory-review, knowledge-capture,
  transaction, session-recap, recovery.
- **Docs** — ARCHITECTURE, API, SECURITY, DATA_MODEL, MIGRATIONS, PLUGIN_GUIDE,
  SKILL_GUIDE, EXTENDING, ROADMAP.

## Principles

Zero cloud · Zero external DB · Zero Docker · Zero network · One-command
install · One-command health · Portable · Deterministic · Human-readable ·
Backward-compatible migrations.

## Layout

```
capt-solo/
├── capt_solo/        # the runtime (core, memory, ctp, khsb, plugin, skills, api)
├── docs/             # 9 documentation files
├── tests/            # pytest suite (>95% public-surface coverage)
├── install.sh        # one-command install
├── doctor.sh         # environment diagnostics
├── uninstall.sh      # remove plugin/skills (+ --purge for data)
├── verify.sh         # one-command health check
└── verify_runtime.py # the verification harness invoked by verify.sh
```

## License

Open-source. See repository for the exact license file.
