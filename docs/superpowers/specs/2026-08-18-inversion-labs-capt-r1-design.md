# Inversion Labs CAPT Edition R1 — Design

**Date:** 2026-08-18
**Status:** APPROVED_FOR_IMPLEMENTATION
**Frozen CAPT base:** `5f2917772e675523176a3112c49e28ffba20b8f1`
**Lab branch:** `feat/inversion-labs-capt-edition-r1`

## 1. Objective

Build a separate Inversion Labs edition of CAPT that restores useful specialist capabilities from bioCAPT, CAPTLang, FrankenCAPT/Forge, and related Inversion Labs work without restoring any legacy authority model. CAPT RuntimeService/EventStore remain the sole authority for governed state, execution lineage, evidence admission, verification, claims, approvals, and completion.

The operator experience should feel like "CAPT with a laboratory full of specialist instruments," not a second runtime bolted beside CAPT.

## 2. Non-negotiable authority invariants

1. No Lab engine may create authoritative CAPT state directly.
2. Every Lab execution is represented by a CAPT `DriverRun` bound to an existing mission/task.
3. Engine output is an observation/advisory, never task completion.
4. Lab output is persisted as an immutable, digest-bound result artifact.
5. CAPT may create a proposed `observation` Claim and attach an `artifact_hash` EvidenceRecord to it.
6. The Claim remains `proposed`; no Lab execution auto-creates a VerificationResult or ClaimGuard decision.
7. A completed Lab DriverRun does not transition the task to `succeeded`, complete a mission, or promote a claim.
8. `trust=capt_authoritative` on EvidenceRecord means CAPT authoritatively recorded the evidence bytes and metadata; it does not mean the engine conclusion is true.
9. Legacy bioCAPT memory, claim, ActionPacket, replay, trust, or kernel authority is not imported.
10. R1 Lab engines are local and no-network by default.

## 3. Architecture

```text
Captain / native CAPT UI / governed command client
                    |
                    v
        RuntimeService command boundary
                    |
          run_lab_engine_advisory
                    |
                    v
          Lab Engine Registry (read-only)
             /       |       |       \
          Math     Analogy  Consensus  Forge
             \       |       |       /
                    v
          structured Lab result artifact
                    |
                    v
     DriverRun -> proposed observation Claim
                    |
                    v
           artifact_hash EvidenceRecord
                    |
         [later, independent verification]
```

`capt_lab` is an extension package and adapter layer. It is not an authority service, state store, mission manager, memory system, or scheduler of record.

## 4. Runtime surface

### Query: `lab_engines`

Returns the installed Lab registry as a read-only projection. Each engine reports:

- `engineId`, `engineVersion`, display name, description;
- supported operations and input constraints;
- epistemic class per operation (`calculation`, `heuristic`, `simulation`, `advisory`);
- filesystem/network requirements;
- donor provenance summary and implementation digest;
- availability/health without claiming scientific validity.

### Command: `run_lab_engine_advisory`

Input:

```json
{
  "missionId": "m-...",
  "taskId": "...-task-N",
  "engineId": "lab.math",
  "operation": "cyclotomic_summary",
  "input": {}
}
```

Command rules:

- authenticated operator command only;
- mission and task must exist and the task must belong to the mission;
- terminal/cancelled tasks reject new Lab execution;
- engine/operation must exist in the live registry;
- payload is canonicalized and digest-bound before execution;
- same idempotency key + same payload returns the durable prior receipt without rerunning;
- same key + different payload fails closed as an idempotency collision;
- unsupported fields/oversized inputs fail before DriverRun creation;
- R1 has no automatic retries for an engine failure.

## 5. Governed execution lifecycle

For an accepted command CAPT allocates deterministic IDs from the command identity:

1. `DriverRun` with `driverId=lab.<engine>` and exact mission/task binding.
2. DriverRun transitions `created -> submitted -> running`.
3. The adapter executes under its declared local/no-network/read-only constraints.
4. Canonical result JSON is written to a bounded Lab staging path.
5. CAPT hashes the exact persisted bytes and verifies the file bytes against that digest before evidence admission.
6. DriverRun transitions to `completed` only after the adapter result is durably materialized.
7. Cognitive-plane authority creates a proposed Claim of kind `observation`.
8. Verification-plane authority constructs an `artifact_hash` EvidenceRecord referencing the exact persisted result bytes and attaches it to the proposed Claim.
9. Receipt exposes IDs/digests/provenance but reports `verificationId: null` and `promotionState: proposed`.
10. Task state is not promoted by the Lab command.

If execution fails before a result artifact exists, DriverRun becomes `failed` and no Claim/Evidence is fabricated. If durable artifact bytes fail digest verification, evidence admission fails closed.

## 6. Lab result artifact

Every engine returns a canonical structure equivalent to:

```json
{
  "schemaVersion": "1.0.0",
  "engineId": "lab.math",
  "engineVersion": "0.1.0",
  "operation": "cyclotomic_summary",
  "epistemicClass": "calculation",
  "requestDigest": "sha256:...",
  "observation": {},
  "limitations": [],
  "driverRunId": "dr-lab-...",
  "missionId": "m-...",
  "taskId": "...-task-N",
  "provenance": {
    "donorRepository": "...",
    "donorCommit": "...",
    "donorPaths": [],
    "donorSourceDigests": [],
    "implementationDigest": "sha256:..."
  }
}
```

The canonical JSON bytes, not an in-memory object, are the evidence artifact. Volatile timestamps may appear outside reproducible observation content but do not change the meaning of an operation result.

## 7. R1 engine catalog

### 7.1 CAPTLang Math — `lab.math`

Donor snapshot: `https://github.com/knowurknottty/biocapt-ecosystem.git` at `28e7834982c859731636e733c53df9f84893f897`.

Validated donor state:

- `cargo test --all-features`: 17 passed, 0 failed;
- `cargo check --all-features`: passed;
- AIMO solver crate `cargo check`: passed.

R1 operations:

- `cyclotomic_summary` — deterministic `calculation`; expose conductor, Euler-phi degree, discriminant where implemented, unit rank, and torsion order. Do not expose placeholder class-group/dlog routines as validated mathematics.
- `mcmillan_tc` — deterministic `calculation` implementing the donor McMillan transition-temperature equation with strict numeric-domain validation.
- `materials_screen` — optional `heuristic`, only if its placeholder/linear nature is disclosed in `limitations`; it must never be labeled a prediction verified by CAPT.
- AIMO routing/solver components remain experimental until operation-specific tests establish what can be honestly exposed.

Known donor limitations include placeholder class-group/dlog, protein-gradient, superconducting predictor, and Eliashberg routines. R1 excludes those from authoritative-looking operations.

Representative donor digests:

- `math/lib.rs`: `sha256:b18cf1ce014f7a949b85dd0aac88beb68ae219ff79e6356bf82a2313caedf740`
- `math/cyclotomic.rs`: `sha256:667939739e81bdfa56fe7baa33a6e47639fbed8b9947a62dbf973e50d62ce6dd`
- `math/materials.rs`: `sha256:add976909138f03297e34968c53419fc9aefd91602a6bf7ad2c3c8dacd8ceb79`

### 7.2 Structural Analogy — `lab.analogy`

Donor: `capt/src/vsa_sme.py` at the same `28e7834...` snapshot; source digest `sha256:54eb6f55debf16ed4fb3b10dacafda1a116d4bbb543d2ddafe5db2576dab3018`.

R1 operations:

- structural mapping / analogy score;
- schema abstraction over bounded user-supplied structures;
- retrieval over an explicitly supplied bounded candidate set.

Required hardening: replace Python's process-randomized built-in `hash()` seed derivation with SHA-256-derived deterministic seeds. Cross-process determinism is an acceptance test. Output class is `heuristic` or `advisory`, never mathematical proof.

### 7.3 QIPC Consensus — `lab.consensus`

Donor: `capt/src/qipc.py`; digest `sha256:5114a890339c3731dc0f4888a33cc68850c092387c4ec180a491950fe993b30b`.

R1 operation: aggregate an explicitly supplied bounded set of beliefs/perspectives into probability/confidence/entropy diagnostics. Output is `advisory`. QIPC does not vote CAPT state into truth, cannot override verification, and does not create mission/task transitions.

NEDA may be reused internally for bounded scheduling later, but it is not a Lab authority or an R1 public engine.

### 7.4 Forge / Invention — `lab.forge`

Primary donor: `frankencapt/frankencapt-base/variants/forge/forge_module.py`; digest `sha256:a0e984cbae5badd32071c98483cacde0717933bfbd173c77f30c624a5b7d7f7f`.

R1 extracts and rewrites only defensible read-only logic:

- bounded repository archaeology;
- requirements/gap synthesis;
- decision-option generation;
- SIGMA implementation brief generation;
- ForgeProof rubric scoring.

ForgeProof Commons rubric donor digest: `sha256:ed0253ba531ba3d6117b3bb2ac6045d34447238e32d08d36198921c19cfe255b`.

The old Sigma invention-swarm/patent scripts are references only. R1 explicitly forbids simulated prior-art searches, invented novelty percentages, fake reviewer consensus, hard-coded confidence, and claims that a generated concept is patentable or novel without real external evidence.

## 8. Forge filesystem security

`lab.forge` is the only R1 engine that may require filesystem read access. It must:

- accept one canonical absolute target root;
- reject root escape, `..`, NUL, and symlink escape;
- never write to target root;
- ignore `.git`, `.env*`, credential/key files, `node_modules`, build/target caches, binaries, and configured secret patterns;
- cap files, bytes, depth, and per-file size;
- canonicalize/redact paths before artifact admission where appropriate;
- have no network access;
- produce no source-file contents in result artifacts unless an operation explicitly requires a bounded excerpt and the excerpt passes secret redaction.

## 9. Packaging and donor provenance

Donor code is copied into `capt_lab/vendor/` only when needed and is accompanied by `capt_lab/donors/manifest.json`. The manifest stores donor repository identity, exact commit when available, relative source paths, source SHA-256 digests, adopted modifications, test status, and known limitations.

The Math adapter may build/use a small local Rust helper binary. The helper accepts canonical JSON on stdin, emits canonical JSON on stdout, has a bounded timeout, receives no credentials, and has no network requirement.

Python package discovery adds `capt_lab*`; CAPT-core packages remain unchanged except for the narrow RuntimeService/command-service integration required to route Lab operations through existing authority.

## 10. Native macOS Lab surface

A new `Labs` sidebar section is a renderer/controller over the runtime query/command boundary. It shows:

- live engine inventory and health;
- operation descriptions and epistemic badges;
- donor provenance/limitations;
- mission/task binding for the active chat;
- structured inputs with bounded validation;
- run action through `run_lab_engine_advisory`;
- resulting DriverRun, Claim, Evidence IDs and artifact digest;
- explicit `UNVERIFIED`, `ADVISORY`, `HEURISTIC`, or `CALCULATION` presentation.

The native app never executes donor code directly.

## 11. Testing and acceptance

R1 is accepted only if all of the following pass:

1. Frozen core regression remains green.
2. Registry output is deterministic and contains exact donor provenance.
3. Unknown engine/operation and malformed inputs fail before DriverRun creation.
4. Mission/task mismatch fails before execution.
5. Same-key/same-payload replay returns the durable receipt and does not rerun the adapter.
6. Same-key/different-payload collision fails closed.
7. Engine failure yields failed DriverRun and no fabricated Claim/Evidence.
8. Successful advisory yields completed DriverRun + proposed observation Claim + artifact-hash EvidenceRecord.
9. Successful advisory yields no VerificationResult, ClaimGuard decision, task success, or mission completion.
10. Artifact tampering/digest mismatch prevents evidence admission.
11. VSA results are deterministic across fresh Python processes.
12. Math donor tests and Lab math adapter tests pass from the vendored source.
13. Forge path traversal/symlink/secret/oversize cases fail closed.
14. Native Labs UI never labels an advisory as verified.
15. Clean installed-wheel and signed-app dogfood executes at least one Math, Analogy, Consensus, and Forge advisory through RuntimeService.

## 12. Explicit R1 exclusions

- no restoration of bioCAPT kernel authority;
- no direct engine writes to authoritative project files;
- no automatic claim acceptance or verification;
- no simulated patent/prior-art authority;
- no remote/network engine execution;
- no unbounded repository ingestion;
- no replacement of CAPT memory/governance/recovery with donor systems;
- no public scientific-validity claims for donor algorithms that have only software tests.

## 13. Cutover criterion

The Lab edition may be called `INVERSION_LABS_R1_DOGFOOD_READY` when all acceptance gates are evidenced on an exact commit/artifact build. That classification means the specialist tools are safely usable for internal work; it does not mean every donor algorithm is scientifically validated or that CAPT-core's public-release bar has changed.
