# CAPT Runtime Plane Convergence — Working Inventory & Convergence Map

Branch: feat/capt-runtime-plane-convergence
Base SHA: 9d4fee12bc6147d7fe5da9e5025e8eb32911293a (origin/main)
Starting HEAD: 52761c47c6d5d75a19012523801e5f959275aab8 (feat/capt-memory-trigger-integration)
Authoritative repo: /Users/knowurknot/CAPT_core
Remote: https://github.com/knowurknottty/CAPT_core.git
Contract version: 1.0.0 (drift clean)
Runtime status: CAPT_RUNTIME_ACTIVE (proven Gate 0)

## Method

Repository evidence supersedes the workflow prose. The inventory below records
ONLY what exists in source/tests/contracts at the starting HEAD. Planned planes
that have no implementation are classified ABSENT/PLANNED and are NOT fabricated.

## Inventory (file :: symbol :: authority owner :: state owner :: persistence :: status)

### Authority & capability (authorization layer — EXISTS)
- capt_runtime/authority.py :: require_authority / permitted_actors / known_acts :: governance_kernel :: none (policy table) :: in-code :: ACTIVE_AND_CANONICAL
- capt_runtime/capability.py :: verify_lease / check_work_order_operations / ALLOWED/DENIED_OPERATIONS :: CAPT (runtime) :: lease state in CapabilityAggregate :: EventStore :: ACTIVE_AND_CANONICAL
- capt_runtime/aggregates/capability.py :: CapabilityAggregate :: CAPT :: capability stream :: EventStore :: ACTIVE_AND_CANONICAL
- contracts/schema/capability.schema.json :: CapabilityGrant / CapabilityLease :: CAPT :: contract :: generated bindings :: ACTIVE_AND_CANONICAL
- contracts/schema/policy.schema.json :: PolicyDecision :: governance :: contract :: generated bindings :: ACTIVE_AND_CANONICAL

### Identity (AUTHENTICATION / PROOF / DELEGATION — ABSENT)
- No Principal, HumanIdentity, AgentIdentity, RuntimeIdentity, DriverIdentity,
  ModelIdentity, SkillIdentity, PluginIdentity, SessionIdentity, Delegation,
  AuthorityChain, IdentityAttestation, RevocationRecord, CapabilitySubject
  contracts exist in contracts/schema/*.
- Driver identity is partially present: drivers/registry.py :: SpoofedDriverIdentity
  (driver-id spoofing guard) and hermes.py :: probe_hermes_identity (executable
  version probe). This is driver-identity attestation only, not a full Identity
  & Authority Plane.
- Status: IDENTITY_PLANE_ABSENT (only driver-identity fragment exists).

### Mission / intent (MissionSpec EXISTS; Mission Compiler ABSENT)
- contracts/schema/mission.schema.json :: MissionSpec :: mission owner :: contract :: generated :: ACTIVE_AND_CANONICAL
- capt_runtime/services.py :: RuntimeService.create_mission / create_mission_with_approval :: mission owner :: MissionAggregate :: EventStore :: ACTIVE_AND_CANONICAL
- NO deterministic Mission Compiler module: intent parsing/normalization is
  embedded in RuntimeService + desktop/m1_command_service.py. No raw-request
  preservation, no unresolved-ambiguity record, no compiler version/digest.
- Status: MISSION_SPEC_ACTIVE; MISSION_COMPILER_ABSENT (logic embedded, not separated).

### Cognitive / planning (ABSENT as separate plane)
- No planner/cognitive module in capt_runtime. Cognition is delegated to drivers
  (Hermes) which are untrusted. Status: COGNITIVE_PLANE_ABSENT.

### Execution (EXISTS)
- capt_runtime/driver_host.py :: DriverHost.dispatch :: execution :: driver-run stream :: EventStore :: ACTIVE_AND_CANONICAL
- capt_runtime/drivers/registry.py :: DriverRegistry :: execution :: registry :: in-memory :: ACTIVE_AND_CANONICAL
- capt_runtime/drivers/openharness.py :: OpenHarnessDriver (reference) :: execution :: none :: n/a :: ACTIVE_AND_CANONICAL
- capt_runtime/drivers/hermes.py :: HermesDriver (external, Mode A) :: execution :: none :: subprocess :: ACTIVE_AND_CANONICAL
- capt_runtime/drivers/__init__.py :: ExecutionDriver Protocol / validate_work_order :: execution :: contract :: generated :: ACTIVE_AND_CANONICAL
- capt_runtime/aggregates/driver_run.py :: DriverRunAggregate :: execution :: driverrun stream :: EventStore :: ACTIVE_AND_CANONICAL
- capt_runtime/reconciliation.py :: reconcile (read-only driver reconciliation) :: execution :: reconciliation record :: EventStore :: ACTIVE_AND_CANONICAL

### State Transition Kernel (PARTIAL — mechanics exist, not named)
- capt_runtime/store.py :: EventStore.commit_command (atomic, versioned, idempotent,
  journaled, replayable), AppendRequest, chain_next (hash chain) :: kernel ::
  event ledger :: SQLite :: ACTIVE_AND_CANONICAL (this IS the kernel mechanics)
- capt_runtime/commands.py :: command()/envelope() (command envelope validation) :: kernel :: n/a :: in-code :: ACTIVE_AND_CANONICAL
- capt_runtime/invariants.py :: by_id (invariant hooks) :: kernel :: n/a :: in-code :: ACTIVE_AND_CANONICAL
- capt_runtime/checkpoint.py :: create_checkpoint/verify_checkpoint/can_dispatch_consequential :: kernel :: checkpoint manifest :: EventStore/JSON :: ACTIVE_AND_CANONICAL
- capt_runtime/replay.py :: full_replay/checkpoint_replay/replay_equivalent :: kernel :: rebuilt state :: EventStore :: ACTIVE_AND_CANONICAL
- Status: KERNEL_MECHANICS_ACTIVE but NOT extracted as a named, domain-neutral
  `StateTransitionKernel` module. Adjudication: EXTRACT/NAME (thin).

### Event Ledger (EXISTS)
- capt_runtime/store.py :: EventStore (events, aggregates, outbox, idempotency, hash chain) :: kernel :: ledger :: SQLite :: ACTIVE_AND_CANONICAL
- contracts/schema/event.schema.json :: EventEnvelope :: kernel :: contract :: generated :: ACTIVE_AND_CANONICAL

### Evidence / Verification / ClaimGuard (EXISTS, distinct)
- capt_runtime/verification.py :: guard_claim (ClaimGuard), build_verification_result,
  verify_artifact, verify_repository_unchanged, verify_no_git_mutation :: evidence :: n/a :: in-code :: ACTIVE_AND_CANONICAL
- contracts/schema/evidence.schema.json :: EvidenceRecord / DriverObservation :: evidence :: contract :: generated :: ACTIVE_AND_CANONICAL
- contracts/schema/verification.schema.json :: VerificationResult :: evidence :: contract :: generated :: ACTIVE_AND_CANONICAL
- contracts/schema/claim.schema.json :: ClaimGuardDecision :: evidence :: contract :: generated :: ACTIVE_AND_CANONICAL
- capt_runtime/aggregates/... :: ClaimAggregate (implied by test_claim.py) :: evidence :: claim stream :: EventStore :: ACTIVE_AND_CANONICAL

### Memory / Data (EXISTS — new this branch)
- capt_runtime/memory/policy.py :: MemoryTriggerPolicy / PolicySource / precedence :: memory :: policy log :: SQLite :: ACTIVE_AND_CANONICAL (this branch)
- capt_runtime/memory/accounting.py :: ContextUsage / TriggerState / estimate_tokens :: memory :: n/a :: in-code :: ACTIVE_AND_CANONICAL
- capt_runtime/memory/store.py :: MemoryStore / MemoryRecord :: memory :: memory store :: SQLite :: ACTIVE_AND_CANONICAL
- capt_runtime/memory/query.py :: build_memory_query :: memory :: n/a :: in-code :: ACTIVE_AND_CANONICAL
- capt_runtime/memory/contextpack.py :: build_context_pack / _select_records :: memory :: pack :: in-code :: ACTIVE_AND_CANONICAL
- capt_runtime/memory/engine.py :: MemoryTriggerEngine :: memory :: trigger log :: SQLite :: ACTIVE_AND_CANONICAL
- contracts/schema/common.schema.json :: MemoryTriggerPolicy / MemoryQuery / MemoryRecord / ContextPack :: memory :: contract :: generated :: ACTIVE_AND_CANONICAL
- capt_solo/memory/* :: MemoryEngine / ContextPack / KnowledgeBubbleRuntime :: disconnected lineage :: n/a :: IMPLEMENTED_DISCONNECTED (NOT imported by capt_runtime)
- Status: DATA_PLANE_MEMORY_ACTIVE (capt_runtime/memory). Knowledge Bubbles: only
  referenced as a concept in workflow; no KnowledgeBubble contract in capt_runtime.
  Vector/graph/SQL/object stores: only SQLite (EventStore + MemoryStore). No vector
  or graph index. Status: DATA_PLANE_PARTIAL (memory + ledger backend only).

### Context selection/reduction/packaging (PARTIAL — exists as one pipeline)
- capt_runtime/memory/contextpack.py :: build_context_pack (selection + reduction + packaging in one function) :: memory :: pack :: in-code :: ACTIVE_BUT_NOT_SPLIT
- capt_runtime/context_slice.py :: build_context_slice / ContextOverDisclosure / _scan_forbidden (driver-facing slice, disclosure guard) :: execution/memory boundary :: n/a :: in-code :: ACTIVE_AND_CANONICAL
- Status: STAGES_PRESENT_BUT_COLLAPSED. Adjudication: SPLIT (thin) per Gate 7.

### Artifact / Workspace (PARTIAL — ingestion exists, no workspace plane)
- capt_runtime/ingestion.py :: validate_observation / validate_artifact_candidate /
  validate_receipt_candidate / reject_fabricated_authoritative / _realpath_within :: artifact ingestion :: n/a :: in-code :: ACTIVE_AND_CANONICAL
- NO WorkspaceDescriptor / WorkspaceLease / ArtifactCandidate / ArtifactRecord /
  ArtifactManifest / MutationReceipt / PathScope / FilesystemPolicy / ArtifactPromotionDecision
  contracts. Status: ARTIFACT_INGESTION_ACTIVE; WORKSPACE_PLANE_ABSENT.

### Learning (ABSENT)
- No Trajectory Store, Reward Compiler, LearningStrategy registry, GRPO/SFT/DPO/
  ORPO/KTO/RLOO, Candidate Registry, Evaluation Harness, Promotion Pipeline,
  Rollback Manager. Status: LEARNING_PLANE_ABSENT.

### Simulation (ABSENT)
- No Simulation Plane, environment digest, dataset digest, isolation marker.
  Status: SIMULATION_PLANE_ABSENT.

### Observability (PARTIAL — diagnostics only)
- capt_runtime/drivers/hermes.py :: diagnostics_json :: observability :: n/a :: in-code :: ACTIVE_BUT_DIAGNOSTIC_ONLY
- No metrics/traces store; logs are not authoritative. Status: OBSERVABILITY_PARTIAL.

### Temporal model (ABSENT as explicit construct)
- Time is used ad hoc (time.strftime RFC3339) in commands/checkpoint/services.
  No TemporalContext, logical/monotonic/causal time distinction. Status: TEMPORAL_MODEL_ABSENT.

### Control/data-plane classification (ABSENT as explicit tagging)
- No control/data-plane tags on commands/events. Capability lease is the closest
  control-plane gate. Status: CONTROL_DATA_PLANE_ABSENT.

### Constitutional Plane (ABSENT)
- No constitutional contract/module. PolicyDecision exists (governance output) but
  no constitutional invariant source. Status: CONSTITUTIONAL_PLANE_ABSENT.

## Convergence map

### reuse (keep as canonical)
- EventStore (State Transition Kernel + Event Ledger)
- RuntimeService (cross-aggregate command surface)
- DriverHost + DriverRegistry + drivers (Execution Plane)
- capability.py + CapabilityAggregate (authorization)
- verification.py (ClaimGuard/Verification/Evidence)
- memory/* (Data Plane memory + ContextPack)
- context_slice.py (driver slice boundary)
- ingestion.py (artifact ingestion)

### extend (thin additions, no replacement)
- Extract StateTransitionKernel as a named, domain-neutral facade over
  store.py/commands.py/invariants.py/checkpoint.py/replay.py (Gate 5).
- Split context pipeline into selection/reduction/packaging stages (Gate 7).
- Add Identity & Authority contracts + thin validation (Gate 3) — only the
  driver-identity fragment exists today.
- Add deterministic Mission Compiler boundary (Gate 4) — extract from embedded logic.
- Add TemporalContext (Gate 13).
- Add control/data-plane classification tags (Gate 12).

### merge
- capt_runtime/memory/* already merged Data Plane memory into capt_runtime
  (replaces disconnected capt_solo/memory lineage). Keep.

### delete / obsolete
- capt_solo/memory/* — IMPLEMENTED_DISCONNECTED; do NOT import. Mark obsolete
  relative to capt_runtime/memory. (No deletion unless evidence supports; it is a
  separate lineage, not dead code in capt_runtime.)

### duplicate
- None confirmed within capt_runtime. The only duplication risk is capt_solo vs
  capt_runtime memory lineage (resolved by convergence: capt_runtime/memory is canonical).

### conflict
- None confirmed. Contract drift is clean.

### unclear
- Whether "Constitutional Plane" should be a separate plane or folded into
  PolicyDecision/governance. Adjudicated in Gate 2 as REJECTED (fold into governance).

## Smallest convergence slice (implementation sequence, Gate 16)
1. Inventory + authority matrix (this doc + CAPT_RUNTIME_PLANE_AUTHORITY_MATRIX.md)
2. Identity & Authority contracts (thin) + driver-identity reuse
3. Deterministic Mission Compiler boundary (extract, not rewrite)
4. State Transition Kernel facade (name existing mechanics)
5. Data Plane boundary (memory already there; add boundary doc)
6. Context selection/reduction/packaging split
7. Artifact/Workspace: ingestion already exists; add thin WorkspaceDescriptor contract + lifecycle gate
8. Event/Evidence/Observability separation (already distinct; document + assert)
9. Simulation Plane M0 (thin isolated harness using existing replay/checkpoint)
10. Learning Plane interfaces (contracts only; no training)
11. TemporalContext
12. Control/data-plane classification
13. Architectural subtraction (none to delete in capt_runtime)
14. Adversarial + reconcile
15. Evidence + PR
