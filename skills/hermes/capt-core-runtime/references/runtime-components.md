# runtime-components.md

What each CAPT Core subsystem is, where it is constructed, and how to verify it
is **operational** rather than merely importable. Never collapse those two.

## 1. The single composition root

`capt_solo.runtime.CAPTRuntime` is the only composition root. Constructed via
`CAPTRuntime.load(configuration)` → `CAPTRuntime(configuration)`, which builds
and owns every subsystem below in `__init__`. There is exactly one per process.

```python
self.engine     = MemoryEngine(db_path=config.db_path)
self.ctp        = CTPRuntime(journal_dir=config.journal_dir)
self.bus        = KHSB()
self.lifecycle  = LifecycleManager(self.engine, bus=self.bus, ctp=self.ctp)
self.proof      = ProofEngine(self.engine._conn)
self.registry   = CapabilityRegistry(self.engine._conn, self.proof)
self.claimguard = ClaimGuard(self.registry, self.proof)
self.gate       = MemoryUseGate(self.engine, ctp=self.ctp, bus=self.bus)
self.events     = _DurableEventLog(self.bus, config.event_log_path, _DURABLE_TOPICS)
```

**You never call any of those constructors.** Verify the invariant instead:

```bash
capt --json agent doctor --workspace "$WS"   # → single_composition_root: true
```

`RuntimeConfiguration` fields: `home db_path journal_dir evidence_dir
event_log_path mission_id`. `from_env()` derives unset fields from
`CAPT_SOLO_HOME`.

`CAPTRuntime` public methods: `load close execute execute_model_task
prepare_external_model_turn commit_external_model_turn abort_external_model_turn`.

## 2. Subsystem reference

### MemoryEngine — `runtime.engine`
SQLite-backed memory store. Records carry `memory_id namespace content tags
provenance confidence tier lifecycle_state retention consent evidence_refs`.

Verify operational: `capt --json memory list --namespace <ns>` returns records
with real ids. An empty store is `EMPTY_MEMORY_STORE`, not a pass.
Also: `capt memory search <query>`, `capt memory inspect|conflicts|pending|
promote|pin|archive|restore|explain`.

### SessionRuntime / LifecycleManager — `runtime.lifecycle`
Session begin/status/checkpoint/resume/consolidate/close.
Verify: `capt --json session list` → sessions with `session_id`,
`project_namespace`, `objective`, `status`, `last_checkpoint`.
`capt session status <id>` for one.

### MemoryUseGate — `runtime.gate`
The mandatory pre-execution gate. Two calls matter:
- `record_selection(mission, objective, records=..., namespace=...)` → selection ids
  for selected / rejected / stale / missing / conflicting.
- `prepare(...)` → `GateDecision` with `.allowed`, `.pack` (the ContextPack),
  `.retrieved` (per-kind memory records), `.block_codes`.

Runtime-enforced: `CAPTRuntime.execute_model_task` calls the gate **before** any
provider invocation. On denial it raises `GateDeniedError` and no provider is
reached.

Verify operational: a boot report with a non-empty `contextpack_digest` and
`gate_result: PASS`. `gate_result: BLOCKED` with `block_codes` is the gate
working, not the gate broken.

### ContextPack — `capt_solo.contextpack`
Bounded, digested context: `MissionIntent`, `RecordRef` evidence, assumptions,
invariants, protected facts, token budget. Digest is `sha256:…` over the pack.

Fidelity is enforced: protected facts derived from evidence (mission id, phase,
head, branch) **must appear in the rendered context** or the gate BLOCKs. That is
the runtime proving recovered state is actually carried into the request — not a
promise that it was.

Verify: `contextpack_digest` present in the boot report, and the same digest in
the persisted boot-trace artifact.

### CTPRuntime — `runtime.ctp`
Transaction journal at `config.journal_dir`. Every governed operation runs inside
a transaction; runtime identity (`runtime_id`, `mission_id`) is recorded in each
transaction's meta.

Verify: a `tx_id` in turn output and a `committed` status. A pending transaction
with no commit/abort is `CTP_INCONSISTENT`.

### KHSB — `runtime.bus`
Event bus plus `_DurableEventLog` writing to `event_log_path`
(default `<CAPT_SOLO_HOME>/data/khsb/events.jsonl`).

Boot publishes: `agent.boot.requested`, `agent.boot.memory_retrieved`,
`agent.boot.context_validated`, `agent.boot.completed`, `agent.boot.failed`.
Turns publish `agent.turn.started`.

Verify: those topics appear in the events log with your run's ids. The log is
append-only and **not hash-chained**.

Note: `CAPT_KHSB_ENABLE=0` in the environment disables it. Check before claiming
`KHSB_NO_EVENTS`.

### ProofEngine — `runtime.proof`
Records typed evidence, e.g. `record("artifact_hash", "agent-boot:<run>", <sha>,
"capt agent boot trace", scope=<mission>)`.

### CapabilityRegistry — `runtime.registry`
Declared capabilities backing ClaimGuard verdicts.
`capt workspace capabilities` lists them.

### ClaimGuard — `runtime.claimguard`
Returns a verdict `{supported: bool, language: str}` for a claim. `supported:
false` means the claim is not backed by registered capability + proof. That is a
correct refusal — do not create a capability or fabricate evidence to flip it.

### ArtifactStore / evidence
Artifacts are written under `config.evidence_dir` (default
`~/.capt/evidence`, or the workspace `.capt/`) with a sibling `.sha256`:
- `agent-boot/<agent_run_id>.json`
- `agent-intent/<intent_id>.json`
- `agent-resume/<mission_id>.json`

Verify: recompute `shasum -a 256 <file>` and compare to the `.sha256` sidecar.
Mismatch is `ARTIFACT_DIGEST_MISMATCH`.
`capt --json evidence status|show|trace|conflicts` inspects the evidence store.

### Mission CheckpointStore — `capt_solo.evidence.CheckpointStore`
Rooted at `<workspace>/.capt/checkpoints/`, one JSON per mission plus
`events.jsonl`. `.capt/` is gitignored — evidence is local-only.

`MissionCheckpoint` fields: `mission_id project_id objective current_phase status
decisions_made constraints acceptance_criteria blockers pending_work
completed_work files_changed commit_references latest_verified_state
latest_evidence_state next_safe_action required_user_decisions
unresolved_invalidations timestamp event_digest`.

Integrity: `event_digest` is a sha256 over the record minus that field.
Recompute to validate. A placeholder digest (64 zeros) fails validation
correctly — the record is wrong, not the validator.

## 3. Agent Runner (ADR-0001, Outcome C) — `capt_solo/agent/`

| module | contents |
|---|---|
| `contracts.py` | frozen v1 dataclasses, `AGENT_SCHEMA_VERSION = "capt.agent.v1"`, execution-mode and output-mode constants, `OutputPolicy`, `IntentRecord`, `AgentBootRequest/Result`, `AgentMemoryBootTrace`, `AgentRunState`, `AgentTurnRequest/Result` |
| `boot.py` | fail-closed boot pipeline: `resolve_workspace`, `resolve_mission`, `resolve_directives`, `validate_checkpoint`, `boot()` |
| `runner.py` | `AgentRunner` (borrows runtime-owned subsystems, constructs none), `resume_report()` |
| `output.py` | `OutputPolicy` rendering; safety/blocker/gate-failure messages always bypass caps |

**Intent is first-class** and is neither memory nor planning: it is the bounded
authorization envelope for ONE execution — goal, owner constraints, allowed and
prohibited scope, completion criteria, output policy. Minted from CAPT state,
persisted as evidence before invocation, never authored by the provider.

## 4. Hermes plugin — `capt_solo/plugin/`

`plugin.yaml` (`kind: standalone`, `entry: __init__.py`, `toolset: capt`) +
`register(ctx)`. Registers 7 hooks:

| hook | governance role |
|---|---|
| `on_session_start` | CAPTRuntime session begin + checkpoint |
| `on_session_end` / `on_session_finalize` | session checkpoint + close |
| `pre_llm_call` | MemoryUseGate + ContextPack injection |
| `post_llm_call` | KHSB model-task event + checkpoint |
| `pre_tool_call` / `post_tool_call` | **OBSERVATIONAL ONLY** |

The plugin holds no runtime state; each hook opens its own `CAPTRuntime`.

Verify loaded: `hermes plugins list` shows `capt-solo` as `enabled`.
Verify parity: `shasum -a 256` on `~/.hermes/plugins/capt-solo/__init__.py` vs
the repo `capt_solo/plugin/__init__.py`. Divergence is `STALE_PLUGIN`.

## 5. Component-state assignment rules

| state | requires |
|---|---|
| `ACTIVE_PRODUCTION_PATH` | an artifact from a real run shows it executed on the production path |
| `ACTIVE_GOVERNANCE_PATH` | it gated, blocked, or recorded a real decision in a real run |
| `TEST_ONLY` | only test fixtures exercise it |
| `AVAILABLE_NOT_WIRED` | importable/constructible, no production call site proven |
| `DEPRECATED` | superseded, retained for compatibility |
| `DEAD_CODE_CANDIDATE` | no call site found and no evidence of use |

An import, a class definition, a passing unit test, or a registered hook proves
`AVAILABLE_NOT_WIRED` at most.
