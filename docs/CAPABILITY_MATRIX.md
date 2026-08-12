# CAPT Capability Matrix

This is the authoritative "what actually exists" table. A feature importing
successfully is **not** proof it is operator-facing. This matrix is the single,
honest view of capability status.

Legend for columns:

- **Implemented** — code exists for it.
- **Tested** — covered by the automated suite (`pytest tests/`).
- **Installed** — available through the shipped `capt` CLI / wheel.
- **Operator-facing** — a normal user can reach it without Python.
- **Internal only** — reachable programmatically but not a user command.
- **Proven** — demonstrated with real artifacts in release evidence.
- **Notes** — pointers and caveats.

Status values: **YES** / **PARTIAL** / **NO**.

| Feature | Implemented | Tested | Installed | Operator-facing | Internal only | Proven | Notes |
|---|---|---:|---:|---:|---:|---:|---|
| Install (`install.sh` + `capt`) | YES | YES | YES | YES | | YES | `install.sh` now installs the `capt` CLI on PATH |
| Verify (`verify.sh`) | YES | YES | YES | YES | | YES | runs `verify_runtime.py` |
| Doctor (`capt doctor`) | YES | YES | YES | YES | | YES | first-class support surface |
| Durable memory store (`capt memory store`) | YES | YES | YES | YES | | YES | new v0.6 command |
| Memory search / list | YES | YES | YES | YES | | YES | |
| Memory lifecycle (pin/archive/promote) | YES | YES | YES | YES | | | expert CLI verbs |
| Runtime start (`capt start`) | YES | YES | YES | YES | | YES | defaults to `~/.capt` |
| Runtime status (`capt status`) | YES | YES | YES | YES | | YES | |
| Runtime stop (`capt stop`) | YES | YES | YES | YES | | YES | |
| Checkpoint (`capt checkpoint`) | YES | YES | YES | YES | | YES | |
| Resume (`capt resume`) | YES | YES | YES | YES | | YES | |
| Evidence / verification view (`capt evidence`) | YES | YES | YES | YES | | YES | |
| EventStore ordered history + replay | YES | YES | YES | PARTIAL | YES | YES | programmatic; via `capt harness` / API |
| Mission creation (governed) | YES | YES | YES | PARTIAL | YES | YES | `capt runtime mission-begin` |
| Approval / govern operator | YES | YES | PARTIAL | PARTIAL | YES | YES | `submit_approval_decision` command op |
| Human approval gate | YES | YES | YES | PARTIAL | YES | YES | |
| CTP transaction / recovery journal | YES | YES | YES | NO | YES | YES | internal |
| Memory Governor / ContextPack policy | YES | YES | YES | NO | YES | YES | internal |
| KHSB in-process coordination | YES | YES | YES | NO | YES | YES | internal |
| Foundry (skills/capabilities) | YES | YES | YES | YES | | | `capt foundry ...` |
| ClaimGuard claim discipline | YES | YES | YES | PARTIAL | | YES | surfaced in `capt evidence` |
| Proof / Verification pipeline | YES | YES | YES | YES | | YES | `capt evidence` |
| DriverHost + bounded drivers | YES | YES | YES | NO | YES | YES | model connectors internal |
| Model provider config (`capt models ...`) | NO | NO | NO | NO | NO | NO | **v0.6 P1** — not yet unified |
| Cross-model continuity demo | YES | YES | YES | PARTIAL | | YES | flagship v0.6 proof (demo 5) |
| Desktop app as default surface | YES | YES | PARTIAL | NO | | | v0.6 P1 decision pending |
| Windows support | NO | NO | NO | NO | NO | NO | unverified |
| Local-model runtime (LM Studio/Ollama/MLX) | PARTIAL | PARTIAL | PARTIAL | NO | | | P1 model provider work |

---

## Reading guide

- **Operator-facing = YES** means you can use it from a `capt` command with no
  Python. Start with the memory and runtime lifecycle rows — those are the v0.6
  P0 on-ramp.
- **Internal only** subsystems (CTP, Memory Governor, KHSB, DriverHost) are real
  and tested but are not things a normal user invokes. Their presence inside the
  architecture is intentional, not a gap.
- **Model provider configuration is the main missing normal-user surface.** The
  runtime can host bounded drivers and the cross-model proof works, but there is
  not yet a unified `capt models list/add/test/use`. That is scheduled P1 work,
  not a silent omission.