# CAPT Core Runtime — User Guide

Skill `capt-core-runtime` (namespace `capt`) boots and resumes the canonical
**CAPT Core (capt-solo)** runtime for any compatible engineering, research,
audit, or build session. It is a *loader and operator guide*, not a reimplementation
of CAPT.

## What it does

- Locates the canonical CAPT installation (editable install → source root).
- Selects the Python interpreter **deterministically** (see portability contract).
- Boots a mission via `capt --json agent status --workspace WS --mission M`.
- Writes and reloads a checkpoint via `capt --json agent checkpoint` / `status`.
- Resumes in a fresh process via `capt --json agent resume` and proves continuity.
- Diagnoses the runtime via `capt-doctor.sh` (18 checks, no false positives).
- Refuses to touch owner CAPT state; isolates into a temp `CAPT_SOLO_HOME`.

## Quick start

```
# From a fresh Hermes (or Orinth) session:
Load CAPT Core and resume mission-project-seal-local-discovery
```

The skill will:
1. Resolve the CAPT install and interpreter.
2. Build a bounded ContextPack and pass MemoryUseGate.
3. Emit a schema-valid boot report.
4. Write a checkpoint, then resume in a fresh process.
5. Report `continuity_verdict` (PROVEN / NOT_PROVEN) and the governance mode.

## Governance honesty

- `capt_execution_mode: GOVERNED` means the **CAPT gate** authorized the boot.
- `hermes_session_mode: BOOTSTRAP_DEGRADED` means Hermes tool hooks are
  **observational** — tool authorization is NOT runtime-enforced in Hermes.
  Do not read GOVERNED as "Hermes enforced this."

## Evidence you can inspect

All runs emit an evidence directory with a `MANIFEST.sha256`. Verify with:
```
shasum -a 256 -c MANIFEST.sha256
python3 -m json.tool 03-boot-report.json
```

See `CAPT_SKILL_ACCEPTANCE_REPORT.md` for the full evidence package.
