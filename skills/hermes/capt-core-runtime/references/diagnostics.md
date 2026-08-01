# diagnostics.md

Twenty diagnostic scenarios. Each: probe → expected → verdict → remedy.
Verdicts are `PASS | WARN | FAIL | NOT_PROVEN`. Never report "available" as
"operational".

`$WS` = workspace root. `$M` = mission id.

---

## 1. CAPT_NOT_FOUND

Probe: `command -v capt`
Expected: a path inside the project venv.
FAIL when empty.

`capt` is not on PATH outside the venv. Remedy:
```bash
cd "$WS" && test -x .venv/bin/capt && source .venv/bin/activate && command -v capt
```
Still empty → `pip show capt-solo`; if absent, the distribution is not installed
in this interpreter. Do not fall back to `python3 capt_cli.py` from a foreign
interpreter.

## 2. WRONG_PYTHON

Probe: `python --version; command -v python`
Expected: the venv interpreter (3.12.x for capt-solo 0.5.0).
FAIL on `/usr/bin/python3` (3.9.6 on macOS) — capt-solo will not import.

## 3. WRONG_VENV

Probe: `python -c "import sys; print(sys.prefix)"`
Expected: `$WS/.venv`.
FAIL when `sys.prefix` is outside the workspace while a `$WS/.venv` exists.
Remedy: `source "$WS/.venv/bin/activate"`.

## 4. WRONG_CHECKOUT

Probe:
```bash
python -c "import capt_solo; print(capt_solo.__file__)"
git -C "$WS" rev-parse --show-toplevel
git -C "$WS" worktree list
```
Expected: `capt_solo.__file__` under the resolved source root; exactly one
candidate.
FAIL when the import resolves to a different checkout (common with multiple
worktrees) or more than one candidate matches.
Remedy: activate the correct venv, or set `CAPT_SOLO_REPO` explicitly. Never
"just use whichever imports first".

## 5. STALE_PLUGIN

Probe:
```bash
shasum -a 256 ~/.hermes/plugins/capt-solo/__init__.py "$WS/capt_solo/plugin/__init__.py"
diff -q ~/.hermes/plugins/capt-solo/plugin.yaml "$WS/capt_solo/plugin/plugin.yaml"
```
Expected: identical digests.
WARN on divergence (the installed copy is authoritative for the running Hermes;
the repo copy is authoritative for the next install).
Note: `plugin.json` alongside `plugin.yaml` is the legacy contract; presence
alone is not a failure.

## 6. MISSION_MISSING

Probe: `capt --json mission status`
Expected: a non-empty `checkpoints` list containing `$M`.
FAIL when `$M` is absent → `MISSION_NOT_FOUND`. Empty list → `MISSION_MISSING`.
Remedy: create one deliberately —
`capt mission checkpoint --mission-id "$M" --project-id "$(basename "$WS")"
--objective "..." --phase "..." --next "..."`. Never invent a mission id to make
boot pass.

## 7. MISSION_AMBIGUOUS

Symptom: `block_codes: ["MISSION_AMBIGUOUS"]`.
This is a **correct refusal**: more than one non-completed mission and no
canonical selector. Never resolve by recency.
Remedy: pass `--mission` explicitly, or complete/close the missions that are no
longer active.

## 8. LEGACY_CHECKPOINT_SCHEMA

Symptom: `ERROR: TypeError: MissionCheckpoint.__init__() missing 2 required
positional arguments: 'project_id' and 'objective'`.

Cause: `boot.resolve_mission` iterates every id in the store and loads each one;
a pre-`project_id`/`objective` record raises instead of being skipped.

Probe which records are legacy:
```bash
for f in "$WS"/.capt/checkpoints/*.json; do
  python - "$f" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
missing=[k for k in ("project_id","objective") if k not in d]
print(f"{sys.argv[1]}: {'LEGACY missing '+','.join(missing) if missing else 'ok'}")
PY
done
```

Remedy: **always pass `--mission`.** Do not mutate old evidence to make discovery
work — that destroys provenance. Migration, if wanted, is a runtime change with
a migration reader, not a skill action.

## 9. SESSION_MISSING

Probe: `capt --json session list`; `capt session status <id>`
Expected: the boot report's `session_id` appears.
WARN when boot returns an empty `session_id` on a non-BLOCKED result.
FAIL when `session status` cannot load the id boot reported.

## 10. EMPTY_MEMORY_STORE

Probe: `capt --json memory list --namespace "$(basename "$WS")"`
Expected: at least one record.
FAIL on `[]` — an empty store means retrieval cannot be proven, so any
"memory-informed" claim is `NOT_PROVEN`.
Check `CAPT_SOLO_HOME` first: an isolated temp home is empty by design.

## 11. GATE_FAILED

Symptom: `gate_result: BLOCKED` with `block_codes`.
This is the gate working. Read the codes; do not retry until the cause is fixed.
Common causes: ContextPack fidelity (protected facts absent from rendered
context), missing evidence refs, unresolved invalidations.
FAIL — and BOOTSTRAP_DEGRADED is NOT an escape hatch: it requires the durable
marker `BOOTSTRAP_DEGRADED_AUTHORIZED` in checkpoint state. Adding that marker to
dodge a gate failure is evidence fabrication.

## 12. INVALID_CONTEXTPACK

Probe: `contextpack_digest` in the boot JSON; cross-check the boot-trace artifact.
Expected: `sha256:` + 64 hex, identical in both.
FAIL when empty, malformed, or mismatched between report and artifact.

## 13. STALE_DIRECTIVE

Probe: compare `active_directive_ids` against repository evidence (ADRs, docs,
`git log`).
CAPT splits `decisions_made` into active vs superseded on explicit markers:
`supersede`, `superseded`, `corrected to`, `rejected`, `overstated`.
WARN when an "active" directive contradicts current repository state — a
superseding decision exists but was recorded without a marker.
Remedy: record the supersession in the checkpoint with an explicit marker. Never
silently ignore a directive you believe is stale.

## 14. CHECKPOINT_MISMATCH

Symptom: `block_codes: ["CHECKPOINT_INTEGRITY"]`, `"checkpoint <id> digest
mismatch"`.

Probe:
```bash
python - "$WS" "$M" <<'PY'
import sys, json
sys.path.insert(0, sys.argv[1])
from capt_solo.evidence import CheckpointStore
st = CheckpointStore(sys.argv[1], create=False)
cp = st.load(sys.argv[2])
p = cp.to_dict().copy(); rec = p.pop("event_digest", "")
print("recorded:", rec)
print("expected:", CheckpointStore._digest(p))
PY
```
A recorded digest of 64 zeros is a placeholder written by an older path.
Other block codes from the same validator: `MISSION_IDENTITY` (checkpoint mission
≠ resolved), `FOREIGN_WORKSPACE` (`project_id` ≠ workspace dir name),
`CHECKPOINT_INCOMPLETE` (no objective).

FAIL. **Do not rewrite the digest.** Fail closed and report. If the mission must
continue, write a NEW checkpoint through `capt mission checkpoint`; leave the
broken record as evidence.

## 15. ARTIFACT_DIGEST_MISMATCH

Probe:
```bash
for f in "${CAPT_SOLO_HOME:-$HOME/.capt-solo}"/../.capt/evidence/agent-boot/*.json \
         "$WS"/.capt/evidence/agent-boot/*.json; do
  [ -f "$f" ] || continue
  echo "$f: recomputed=$(shasum -a 256 "$f" | cut -d' ' -f1) sidecar=$(cut -d' ' -f1 < "$f.sha256" 2>/dev/null)"
done
```
Sidecars are `sha256:<hex>  <name>`. Mismatch = FAIL; preserve both, do not
regenerate.

## 16. CTP_INCONSISTENT

Probe: inspect the CTP journal dir (`RuntimeConfiguration.journal_dir`, default
under `CAPT_SOLO_HOME`). A turn should end `committed`.
WARN on a pending transaction with no commit/abort. FAIL if a governed operation
claims success with no `tx_id`.

## 17. KHSB_NO_EVENTS

Probe:
```bash
echo "CAPT_KHSB_ENABLE=${CAPT_KHSB_ENABLE:-<unset>}"
tail -5 "${CAPT_SOLO_HOME:-$HOME/.capt-solo}/data/khsb/events.jsonl"
```
Expected topics for a boot: `agent.boot.requested`, `agent.boot.memory_retrieved`,
`agent.boot.context_validated`, `agent.boot.completed`.
`CAPT_KHSB_ENABLE=0` ⇒ verdict `NOT_PROVEN`, not FAIL — the bus is deliberately
off. Otherwise absence of events after a successful boot is FAIL.

## 18. CLAIM_UNSUPPORTED

Probe: the `claim_verdict` in turn output; `capt --json evidence trace <claim>`.
`supported: false` is a correct refusal. Verdict FAIL for the claim, PASS for
ClaimGuard.
**Never** register a capability or manufacture evidence to flip a verdict.

## 19. PLUGIN_NOT_LOADED

Probe: `hermes plugins list | grep -i capt-solo`; check `plugins.enabled` in
`~/.hermes/config.yaml`.
Expected: `enabled`.
FAIL when absent or `not enabled`. Also check `plugin.yaml` exists in
`~/.hermes/plugins/capt-solo/` — the legacy `plugin.json`-only shape is not
loaded by the current Hermes loader.
Consequence when not loaded: no `pre_llm_call` gate in the Hermes path. Report
`hermes_session_mode: BOOTSTRAP_DEGRADED` with
`MemoryUseGate enforced by runtime: NO`.

## 20. COMPACTION_BEFORE_HANDOFF

Symptom: the Hermes session compacted its transcript before a CAPT checkpoint was
written and verified.
Verdict: continuity is `NOT_PROVEN` — label it **fallback continuity**, never
CAPT memory success.
Remedy: write the checkpoint immediately, verify it reloads
(`capt --json agent status --workspace "$WS" --mission "$M"`), then start a fresh
process and recover through `capt --json agent resume`. Do not carry a compacted
summary forward as if it were recovered state.

---

## Verdict discipline

| verdict | meaning |
|---|---|
| `PASS` | probed, and an artifact or CLI output proves the behaviour |
| `WARN` | works, but a condition will cause failure later |
| `FAIL` | probed and broken |
| `NOT_PROVEN` | not probed, unprobeable here, or deliberately disabled |

`NOT_PROVEN` is the honest default. It is never an implied `PASS`.
