# Triple Recursion — Pass 3: Full-System Reaudit, Cleanup, Packaging, Evidence Refresh, Merge Readiness

## Re-read of changed code (from scratch)

All bridge modules were re-read after the Recursion 2 edits:

- `protocol.py` — `TurnEnvelope` (strict structural validation, `auth` defaults to
  `""` so missing-auth is distinct from malformed), `BridgeConnectionDescriptor`
  (runtime-scoped token, env-only delivery), `TurnReceipt` (per-turn ownership
  proof), `BridgeProtocolError` (machine-readable codes). No dead code.
- `lease.py` — atomic `O_CREAT|O_EXCL` acquisition, fencing token, generation,
  PID/pgid/hostname, stale recovery, ownership-checked release. `fences()` is
  correct (higher generation OR same generation + higher token).
- `continuity.py` — schema_version=1 metadata, atomic write (temp+fsync+rename),
  integrity digest, mission/checkpoint binding, rollback rejection, legacy `.sid`
  migration, structured `ContinuityError` codes (MISSING vs CORRUPTED vs
  MISSION_MISMATCH vs CHECKPOINT_MISMATCH vs ROLLBACK_DETECTED vs WRITE_FAILED).
- `runner_process.py` — launcher assigns `runtime_id`/`runtime_generation` up front,
  issues `CAPT_BRIDGE_TURN_AUTH` via env (never argv), atomic lease, deterministic
  AF_UNIX path (≤104 bytes), bounded stdout/stderr capture, `start_new_session`
  for signal propagation.
- `serve.py` — authenticated turn channel (hmac, replay set, bounds), per-turn
  ownership receipt, fail-closed provider path (no Hermes fallback), bounded read
  loop that drains oversized bodies (no client deadlock). **Fixed in reaudit:**
  the manual-launch fallback no longer disables auth — it mints a fresh token and
  logs it (an unauthenticated turn channel is never acceptable).
- `turn.py` — client sends authenticated `TurnEnvelope`, surfaces the per-turn
  receipt digest, never substitutes a Hermes answer.
- `boot_bridge.py` — continuity-backed session recovery with diagnostic log on
  failure (fail-closed: returns `""` if continuity cannot be verified).
- `capt_solo/api.py` — re-exports the canonical `CAPTRuntime`,
  `RuntimeConfiguration`, `GateDeniedError` (real implementations, no aliases).
- `capt_solo/foundry/claimguard.py` — verified-capability claim verdict now
  respects the live proof aggregate (fixed `supported=True` on unsatisfiable
  aggregate).

## Normalized PR scope and generated evidence

- The branch bundles runtime-skill reconciliation (R1) and bridge hardening (R2).
  Evidence is normalized to: one acceptance manifest, one adversarial matrix
  (28 tests), one external replay record (the acceptance harness), compact docs.
- Removed from consideration: transient logs, raw sockets, local PIDs, repeated
  near-identical acceptance directories. The `broken-capt` fixture is a legitimate
  fail-closed test fixture (a deliberately broken CAPT source tree) and is kept.
- `.gitignore` already excludes `__pycache__`, `*.egg-info`, build artifacts.

## Verification run (local CI-equivalent)

- `python -m compileall capt_solo tests` — clean.
- `python -m build` — wheel `capt_solo-0.5.0-py3-none-any.whl` built
  (sha256=7d2ffe89dce6a2297982937034af1242a6390b263b726ee56f09fa0fd6a18477).
- Installed-wheel smoke test — clean venv install; `capt_solo.api` +
  `capt_solo.bridge.*` all import; `CAPTRuntime.load` present.
- `pytest tests/test_runtime_composition.py tests/test_model_task.py
  tests/test_model_task_acceptance.py` — 28 passed (the three collection-failing
  modules from the original CI failure are now green).
- `pytest tests/test_bridge_bootstrap.py tests/test_bridge_adversarial.py` — 90
  passed.
- `python tests/acceptance_bridge.py` — 3 scenarios passed (success / failure /
  ownership-denial), including authenticated turn routing through the live runner.
- Secret scan — no hardcoded keys/tokens; launch nonce + turn auth delivered via
  env only; `LM_STUDIO_API_KEY`/`CAPT_MODEL_API_KEY` only via `os.environ` allowlist.
- Absolute-path scan — no `/Users/`, `/tmp/`, `/private/var` in bridge source.
- `git diff --check` — clean.

## Known limitations (honest)

1. **Pre-existing `test_v04_cli.py` failures (20 tests) are OUT OF SCOPE for this
   reconciliation.** They fail because the v0.4 foundry CLI (`_cmd_foundry`) calls
   `mgr._eng`, a private attribute that does not exist on the v0.5 `CAPTRuntime`
   (which exposes `engine`). This is a v0.4↔v0.5 foundry-CLI compatibility gap in a
   different subsystem, NOT one of the 14 listed defects, and was failing on the
   base commit before this work. Fixing it requires updating the foundry CLI to
   the v0.5 public API (a separate workstream). The mission forbids adding
   compatibility aliases that conceal missing architecture, so no `_eng` shim was
   introduced. **These 20 failures will block the CI "enforce test suite" gate.**
2. Lease heartbeat is written at acquisition only; a long-lived runner does not
   currently refresh `last_heartbeat` on an interval. Stale recovery relies on PID
   liveness + the 30s window from acquisition.
3. The live-runner turn path requires a CAPT provider (`CAPT_MODEL_ENDPOINT`);
   without one the turn returns a structured `CAPT_AGENT_RUNNER` failure (no
   Hermes fallback) — correct, but model text is not produced in CI without a
   model server.

## Merge recommendation

The 14 listed defects are fully remediated and proven by fresh-process,
adversarial, and acceptance tests. The branch is NOT merge-ready for CI-green
because of the 20 pre-existing, out-of-scope `test_v04_cli.py` failures. Those must
be resolved (or explicitly scoped out of the merge gate by the owner) before the
PR can be marked ready. Recommendation: **MERGE_BLOCKED** until the foundry-CLI
compatibility gap is addressed in a separate PR, or the owner confirms those tests
are out of the merge gate for this reconciliation.
