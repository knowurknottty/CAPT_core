# CAPT Solo v0.5.0

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
  metadata, semantic-search adapter interface, export/import, backups, forward-only
  migration with backup-gated safety.
- **CTP Runtime** — append-only transaction journals with receipts, idempotency,
  correlation ids, audit trail, and crash recovery.
- **KHSB** — in-process message bus (publish/subscribe/request/reply/timeout/ack).
- **Foundry** — proof-governed skill/capability/bubble lifecycle (validation,
  proof aggregation, ClaimGuard scoped degradation, 12-step bubble validation,
  governance CTP-bounded audit).
- **Canonical subsystems** — episodic/ECHO, semantic, procedural, prospective,
  autobiographical, HMC, ENGRAM, DREAM, replay, consent, local sync, continuous
  learning, research adapters (optional, degrade independently).
- **Hermes Plugin** — 46 stable public tools (`capt_store_memory`, …,
  `capt_verify_claim`, `capt_build_bubble`, …).
- **Universal Workspace** — the repository is self-describing. Start at
  `AGENTS.md`; resume via `CURRENT_STATE.md` and `CHECKPOINT.md`; operate via
  `capt workspace` (status/validate/bootstrap/checkpoint/tasks/next/capabilities).
- **Engines** — bounded, safe, defensible public engines:
  - **Mathematics** (`capt_solo.engines.mathematics`) — safe AST parser (no
    `eval`/`exec`), exact `Fraction` arithmetic, approximate arithmetic with
    uncertainty propagation, dimensional quantities over 7 SI base dims,
    structural-affine linear solving, extrema-safe intervals, derivation traces.
  - **Physics** (`capt_solo.engines.physics`) — built on the math substrate;
    classical mechanics, basic thermodynamics, elementary circuits, waves. Every
    relation is explicitly classified (established law / model / approximation /
    empirical / hypothesis / speculative); dimensional validation enforced.
  - **Invention** (`capt_solo.engines.invention`) — structured 17-step workflow
    with explainable feasibility scoring, constraint tracking, contradiction
    detection, safety gates, and revision history. Integrates math/physics
    results directly. No patentability claims.
  - **Memory convergence** — explicit 14-type memory taxonomy
    (`capt_solo.memory.types`): Event/Observation/Episode/Interpretation/
    Inference/Belief/Identity Narrative/Autobiographical/Semantic/Revision/
    Correction/Supersession/Provenance/Replay. Non-destructive revision, provenance
    chains, quarantine of malformed data, DREAM output labeled inferred (never
    silently overwrites canonical memory).
  - **PULSE** (`capt_solo.pulse`) — optional LLM gateway, **disabled by default**,
    no network on import, fails closed. Not enabled unless explicitly configured.
- **Docs** — `docs/` holds the canonical architecture, ADRs, subsystem docs, and
  evidence reports. Root `CAPT_CANON.md`, `CANONICAL_ARCHITECTURE.md`,
  `CANONICAL_OWNERSHIP_MATRIX.md` are pointers to the canonical sources.

## Principles

Zero cloud · Zero external DB · Zero Docker · Zero network · One-command
install · One-command health · Portable · Deterministic · Human-readable ·
Backward-compatible migrations · Workspace-native (no giant bootstrap prompt).

## Layout

```
capt-solo/
├── AGENTS.md                 # universal agent entrypoint (authority order + startup)
├── CAPT_CANON.md             # pointer → docs/CAPT_CANON.md (constitutional invariants)
├── CANONICAL_ARCHITECTURE.md # pointer → docs/CANONICAL_ARCHITECTURE.md
├── CANONICAL_OWNERSHIP_MATRIX.md # pointer → docs/CANONICAL_OWNERSHIP_MATRIX.md
├── WORKSPACE.md              # workspace contract (state classes, permissions)
├── CURRENT_STATE.md          # authoritative live state
├── CHECKPOINT.md             # immediate resume contract
├── TASK_QUEUE.md             # human-readable task queue
├── SECURITY_BOUNDARIES.md    # trust model + untrusted-content handling
├── TOOLING.md                # workspace CLI reference
├── RELEASE_STATE.md          # release readiness
├── architecture/             # registry.yaml + JSON schemas
├── capt_solo/                # the runtime (core, memory, ctp, khsb, foundry, plugin, skills, api, workspace, evidence)
├── docs/                     # canonical architecture, ADRs, evidence, subsystem docs
├── tests/                    # pytest suite (594 tests + evidence suite)
├── capt_cli.py               # CLI (memory/session/procedure/prospective/retrieval/canon/foundry/architecture/workspace/verify/evidence/mission/selfmod)
├── verify_runtime.py         # 46-check structured verification harness
├── doctor.sh / verify.sh / install.sh / uninstall.sh
└── pyproject.toml            # version 0.5.0, MIT
```

## Verification

```bash
python3 -m pytest -q            # full suite (594 passed + evidence suite)
python3 verify_runtime.py       # 46 structured checks
python3 architecture/validate_registry.py   # registry fitness
python3 capt_cli.py workspace validate       # workspace consistency
python3 capt_cli.py verify status            # VSI verification state
python3 capt_cli.py evidence status          # evidence store summary
```

## Evidence Engine

The governed evidence layer (`capt_solo/evidence/`) distinguishes what is
present / believed / inferred / attempted / changed / verified / valid /
invalidated / project-local / globally-reusable — these concepts do not collapse
into one field. It provides proof-preserving evidence reuse (VSI integration),
first-class invalidation events, project workspace isolation, scoped
memory-promotion boundaries, self-modification governance, mission checkpoint/
restart recovery, and long-session efficiency controls. See `docs/EVIDENCE_MODEL.md`
and `docs/VSI_MODEL.md`.

## License

MIT. See `LICENSE`.
