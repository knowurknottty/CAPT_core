# CAPT Runtime Plane Adjudication (Gate 2)

Branch: feat/capt-runtime-plane-convergence
Method: repository evidence supersedes workflow prose. A plane is accepted only
if source/tests/contracts prove unique authority, unique state, OR distinct
failure semantics. Diagram-only abstractions are rejected.

## Adjudication table

| Proposed plane | Evidence in repo | Unique authority? | Unique state? | Distinct failure? | Decision |
|---|---|---|---|---|---|
| Identity & Authority | driver-identity fragment only (registry.SpoofedDriverIdentity, hermes.probe_hermes_identity); NO Principal/HumanIdentity/AgentIdentity/RuntimeIdentity/DriverIdentity/ModelIdentity/SessionIdentity/Delegation/AuthorityChain/IdentityAttestation/RevocationRecord/CapabilitySubject contracts | YES (who acts under what authority) — but unimplemented beyond driver id | YES (delegation/revocation records) — unimplemented | YES (spoof/revoke/replay) | ACCEPT (thin; define contracts + reuse driver-identity) |
| Constitutional | NO constitutional module/contract. Governance exists (authority.require_authority, PolicyDecision contract, invariants.by_id) | NO unique authority beyond governance | NO unique state beyond policy | NO distinct failure beyond governance | REJECT as separate plane; fold into governance/PolicyDecision + Identity&Authority authorization |
| Cognitive | NO cognitive/planner module in capt_runtime. Cognition delegated to untrusted drivers (Hermes) | NO CAPT-owned authority | NO CAPT-owned state | NO distinct CAPT failure (driver is untrusted, Execution Plane) | REJECT as CAPT-owned plane; cognition lives in Execution Plane drivers (untrusted) |
| Execution | DriverHost, DriverRegistry, OpenHarnessDriver, HermesDriver, DriverRunAggregate, ExecutionDriver Protocol, reconciliation | YES (what authorized action, by which driver) | YES (driverrun stream) | YES (driver failure/timeout/reconciliation) | ACCEPT (canonical) |
| Evidence | verification.py (guard_claim/build_verification_result/verify_*), EvidenceRecord/VerificationResult/ClaimGuardDecision/DriverObservation contracts, ClaimAggregate | YES (what evidence supports which claim) | YES (evidence/claim streams) | YES (unverified ≠ verified) | ACCEPT (canonical, distinct from Event Ledger) |
| Data | memory/* (MemoryStore/Policy/Query/ContextPack/Engine), EventStore backend, SQLite | YES (durable truth/memory/context material) | YES (memory store + ledger) | YES (data loss/corruption vs logic failure) | ACCEPT (canonical) |
| Artifact / Workspace | ingestion.py (validate_artifact_candidate/validate_observation/reject_fabricated_authoritative/_realpath_within); NO WorkspaceDescriptor/Lease/ArtifactRecord/Manifest/MutationReceipt/PathScope/FilesystemPolicy/PromotionDecision | YES (what concrete object changed, can it be promoted) | YES (staging/snapshot state) | YES (path escape/promotion-without-verification) | ACCEPT (thin; extend ingestion with WorkspaceDescriptor + lifecycle gate) |
| Learning | NO Trajectory/RewardCompiler/LearningStrategy/GRPO/SFT/DPO/ORPO/KTO/RLOO/Candidate/Eval/Promotion/Rollback | n/a (absent) | n/a | n/a | ACCEPT interfaces only (contracts; NO training, NO auto-promotion) |
| Simulation | NO simulation plane/environment digest/dataset digest/isolation marker | n/a (absent) | n/a | n/a | ACCEPT M0 (thin isolated harness reusing replay/checkpoint; no production authority) |

## Kernels / services (NOT planes)
- State Transition Kernel: mechanics exist in store.py/commands.py/invariants.py/checkpoint.py/replay.py. ACCEPT as a named, domain-neutral facade (extract, do not rewrite).
- Mission Compiler: MissionSpec contract exists; compilation logic embedded in RuntimeService + desktop/m1_command_service.py. ACCEPT as explicit deterministic boundary (extract, do not rewrite).
- Event Ledger: EventStore. Part of State Transition Kernel, not a plane.

## Frozen plane count (after Gate 2)

ACCEPTED PLANES (7):
1. Identity & Authority
2. Execution
3. Evidence
4. Data
5. Artifact / Workspace
6. Learning (interfaces only)
7. Simulation (M0)

REJECTED AS PLANES (folded, with evidence):
- Constitutional → folded into governance (authority.py + PolicyDecision + invariants.py)
- Cognitive → folded into Execution Plane (untrusted drivers; CAPT does not own cognition)

KERNELS/SERVICES (not planes): State Transition Kernel, Mission Compiler, Event Ledger.

Plane count is FROZEN at 7. No further plane may be added without new repository
evidence proving unique authority, unique state, AND distinct failure semantics
that cannot be owned by an existing plane.
