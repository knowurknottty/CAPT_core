# 06 — API and Source Atlas

This page maps the current implementation so an operator/developer can locate every major functional surface without treating every internal helper as a public promise.

## Composition and contracts

| Module | Types/functions | What it does |
|---|---|---|
| `capt_runtime/contracts.py` | `canonical_json`, `digest`, `require` | canonical JSON, SHA-256-style contract digests, JSON-schema validation |
| `capt_runtime/commands.py` | `fingerprint`, `command`, `envelope` | command fingerprints and metadata/envelopes |
| `capt_runtime/composition.py` | `RuntimeComposition`, `create_runtime` | wires EventStore, RuntimeService, driver registry/host, task resolver; builds Hermes/provider hosts |
| `capt_runtime/authority.py` | `permitted_actors`, `require_authority`, `known_acts` | actor/act authority checks |
| `capt_runtime/capability.py` | `canonical_operation`, `is_allowed_operation`, `is_denied_operation`, `verify_lease`, `check_work_order_operations` | capability operation and lease enforcement |
| `capt_runtime/context_slice.py` | `ContextOverDisclosure`, `build_context_slice` | minimized driver context, forbidden-field scan |
| `capt_runtime/ingestion.py` | `validate_observation`, `validate_artifact_candidate`, `validate_receipt_candidate`, `reject_fabricated_authoritative` | validates untrusted driver returns |
| `capt_runtime/invariants.py` | `by_id` | named runtime invariants |
| `capt_runtime/temporal.py` | `now_iso`, temporal/causal helpers | timestamp and causal order validation |
| `capt_runtime/identity.py` | principal/session/delegation/revocation validators | identity/authority-chain validation |

## Durable Core

| Module | Types/functions | What it does |
|---|---|---|
| `capt_runtime/store.py` | `EventStore`, `AppendRequest`, `chain_next` | SQLite append ledger, chain integrity, idempotency persistence |
| `capt_runtime/services.py` | `RuntimeService` | authoritative aggregate command API |
| `capt_runtime/kernel.py` | command/event builders, `commit_transition`, invariant evaluation, checkpoint/replay helpers | orchestration primitives |
| `capt_runtime/replay.py` | `ReplayState`, `full_replay`, `checkpoint_replay`, `replay_equivalent` | deterministic state reconstruction |
| `capt_runtime/checkpoint.py` | create/verify checkpoint, dispatch guard | durable recovery manifests |
| `capt_runtime/reconciliation.py` | `reconcile` | observation/reconciliation decision mechanics |
| `capt_runtime/driver_run.py` | `DriverRunAggregate` | standalone driver-run aggregate implementation |

## Aggregates

| File | Aggregate | Owns |
|---|---|---|
| `aggregates/mission_task.py` | `MissionAggregate`, `TaskAggregate` | mission/task state machine |
| `aggregates/capability.py` | `CapabilityAggregate`, `scope_contains` | grants, leases, reservations, consumption and scope containment |
| `aggregates/claim_driver.py` | `ClaimAggregate`, `DriverRunAggregate` | claims and driver lifecycle states |
| `aggregates/human_approval.py` | `HumanApprovalAggregate` | approval request/decision state |

## Driver boundary

| Module | Types/functions | What it does |
|---|---|---|
| `drivers/__init__.py` | `ExecutionDriver` protocol, work-order/descriptor validation | common driver contract |
| `drivers/registry.py` | `DriverRegistry` and registry errors | descriptor registration/version/identity checks |
| `driver_host.py` | `DriverHost`, `tree_digest` | selected-driver lifecycle boundary and target digesting |
| `drivers/provider.py` | `ProviderDriver`, `ProviderDriverFailure` | governed Ollama/OpenRouter transport and safe provenance |
| `drivers/hermes.py` | `HermesDriver`, executable/identity/env/prompt helpers | bounded external Hermes execution |
| `drivers/openharness.py` | `OpenHarnessDriver` | deterministic/reference driver |
| `task_resolver.py` | `TaskResolver`, `ResolvedExecutionTask` | retrieves authoritative execution objective |

## Verification, artifact, and lifecycle support

| Module | Functions/classes | Purpose |
|---|---|---|
| `verification.py` | repository/git/artifact checks, `guard_claim`, evidence/verification builders | independent evidence and claim support/contradiction |
| `artifact_workspace.py` | descriptor/candidate/promotion validation, stage/decide/rollback | bounded artifact workspace operations |
| `cli_ramp.py` | `default_state_dir`, `default_paths`, `is_running` | normal local CLI state resolution |
| `control_data_plane.py` | `classify`, `tag_command`, control-channel assertion | separates control/data operations |
| `session.py` | `SessionLifecycle` | runtime session continuity helpers |
| `mission_compiler.py` | `compile_mission` | raw-request to mission spec compilation |

## Discovery and context

| Module | Key surface |
|---|---|
| `context_pipeline.py` | bubble/record selection, reduction, ContextSlice and ContextPack packaging |
| `memory/engine.py` | `MemoryTriggerEngine` |
| `memory/governor.py` | `MemoryGovernor` |
| `discovery/__init__.py` | `run_discovery`, `to_evidence` |
| `discovery/scanner.py` | `BoundedLocalScanner` |
| `discovery/governor.py` | `DiscoveryGovernor` |
| `discovery/policy.py` | `ClassificationPolicy` |
| `discovery/redaction.py` | `redact_text`, `redact_jsonl`, `normalize_path`, `redact_json` |
| `discovery/provenance.py` | run and observation provenance constructors |

## Operator and UI source map

| Module | Purpose |
|---|---|
| `capt_cli.py` | public `capt` argparse groups/ramp/run/tui entry |
| `capt_ui/operator/cli.py` | public `capt-ui` groups |
| `capt_ui/operator/providers.py` | persisted validated provider registry and health probing |
| `capt_ui/operator/adapters.py` | native/Ollama/OpenAI-compatible/subprocess health/model adapter layer |
| `capt_ui/operator/secrets.py` | references, resolution, safe scrubbing |
| `capt_ui/operator/models.py` | provider/model preferences and precedence |
| `capt_ui/operator/openrouter_models.py` | approved-label catalog plus unambiguous text model selection |
| `capt_ui/operator/provider_support.py` | honest capability/support matrix |
| `capt_ui/operator/runtime.py` | UI operator client facade |
| `capt_ui/operator/bootstrap.py` | state/socket/token path resolution |
| `capt_ui/surfaces/tui/app.py` | `CaptTUI` interactive Textual surface |

## Desktop socket source map

| Module | Purpose |
|---|---|
| `desktop/capt_runtime_service.py` | runtime server, query service, startup recovery, provider/Hermes runner |
| `desktop/m1_command_service.py` | receipt/idempotency-facing command service |
| `desktop/desktop_runtime_client.py` | authenticated local client and projections |
| `desktop/desktop_app.py` | desktop/headless visual app helpers |

## Schema reading order

Canonical JSON schemas sit under `contracts/schema/`. Begin with:

```text
common.schema.json
command.schema.json
mission.schema.json
capability.schema.json
driver.schema.json
verification.schema.json
```

`driver.schema.json` is especially relevant to provider/Hermes work: ContextSlice and ExecutionDriverWorkOrder reject extra fields and freeze the driver isolation boundary.

## Tests as executable map

Useful current regression groups:

```text
tests/capt_runtime/test_ouroboros_lifecycle.py
tests/capt_runtime/test_model_operator.py
tests/capt_runtime/test_provider_driver.py
tests/test_ui_provider_support.py
tests/test_ui_operator_layer.py
tests/test_ui_cli.py
tests/capt_runtime/
tests/
```

Tests prove particular cases, not a license to bypass contracts or invent undocumented execution paths.
