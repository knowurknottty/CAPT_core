# Inversion Labs CAPT R1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a separate Inversion Labs specialist-engine edition to the frozen CAPT base while preserving RuntimeService/EventStore as the sole authority and admitting specialist output only as proposed observation claims plus digest-bound evidence.

**Architecture:** A new `capt_lab` package owns engine registry, donor provenance, bounded adapters, and canonical result artifacts. RuntimeService command/query integration represents every advisory as a CAPT DriverRun and records successful results through the existing Claim/Evidence boundary; the native Labs view is only a renderer/controller over those runtime operations.

**Tech Stack:** Python 3.8+, CAPT RuntimeService/EventStore, pytest, NumPy where already declared/needed, Swift 6/SwiftUI, macOS local IPC, canonical JSON + SHA-256. Rust donor code remains provenance/reference unless a later acceptance gate justifies shipping a helper binary.

**Spec:** `docs/superpowers/specs/2026-08-18-inversion-labs-capt-r1-design.md`

## Global Constraints

- Frozen base is `5f2917772e675523176a3112c49e28ffba20b8f1`; do not weaken its provider, approval, replay, evidence, verification, or task-lineage semantics.
- Lab output is advisory/observational and never auto-verifies, auto-accepts a claim, succeeds a task, or completes a mission.
- R1 Lab engines are local and no-network by default.
- Every successful result is canonical JSON with request digest, implementation digest, donor SHA/path/digests, epistemic class, mission/task/DriverRun IDs, observation, and limitations.
- Forge is read-only and root-bounded with path/symlink/secret/size protections.
- Same idempotency key + same payload must not rerun an engine; same key + different payload must fail closed.
- Public scientific validity is never inferred from software tests.

---

## File Structure

Create:

- `capt_lab/__init__.py` — public Lab package exports.
- `capt_lab/contracts.py` — Lab request/result validation and canonicalization.
- `capt_lab/provenance.py` — SHA-256/source provenance helpers.
- `capt_lab/registry.py` — immutable engine descriptors and dispatch lookup.
- `capt_lab/engines/base.py` — engine protocol/result helpers.
- `capt_lab/engines/math_engine.py` — bounded deterministic Math operations.
- `capt_lab/engines/analogy.py` — deterministic VSA structural analogy adapter.
- `capt_lab/engines/consensus.py` — bounded QIPC consensus adapter.
- `capt_lab/engines/forge.py` — bounded repository archaeology/gap/ForgeProof adapter.
- `capt_lab/donors/manifest.json` — exact donor SHA/path/digests/limitations.
- `tests/capt_lab/` — focused unit/security/runtime tests.
- `capt_ui/surfaces/desktop_swift/Sources/CAPTCoreDesktop/CAPTLabModels.swift` — native typed Lab projections.
- `capt_ui/surfaces/desktop_swift/Sources/CAPTNativeMac/Views/LabsView.swift` — native Labs surface.
- `capt_ui/surfaces/desktop_swift/Tests/CAPTCoreDesktopTests/CAPTLabProjectionTests.swift` — native Lab projection tests.

Modify:

- `pyproject.toml` — include `capt_lab*` in package discovery.
- `desktop/m1_command_service.py` — expose `lab_engines` and `run_lab_engine_advisory` plumbing without bypassing RuntimeService.
- `desktop/capt_runtime_service.py` — wire the Lab registry/runner into the authenticated server.
- native `CAPTBackgroundRuntime.swift`, `CAPTOperatorStore.swift`, sidebar/content views — query/run Lab operations through IPC.
- native README/status docs — describe bounded Lab edition accurately.

---

### Task 1: Lab contracts, donor manifest, and immutable registry

**Files:**
- Create: `capt_lab/contracts.py`
- Create: `capt_lab/provenance.py`
- Create: `capt_lab/registry.py`
- Create: `capt_lab/engines/base.py`
- Create: `capt_lab/donors/manifest.json`
- Create: `tests/capt_lab/test_registry.py`
- Create: `tests/capt_lab/test_lab_contracts.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces `LabEngineRequest`, `LabEngineResult`, `canonical_json_bytes(value)`, `sha256_digest(bytes)`, `LabEngineDescriptor`, `LabEngineRegistry.describe()`, and `LabEngineRegistry.execute(request, context)`.
- Later tasks register adapters using `register(descriptor, engine)` and return `LabEngineResult` only.

- [ ] **Step 1: Write failing contract and registry tests**

```python
def test_request_digest_is_order_independent():
    a = canonical_request_digest({"engineId":"lab.math","operation":"x","input":{"b":2,"a":1}})
    b = canonical_request_digest({"operation":"x","input":{"a":1,"b":2},"engineId":"lab.math"})
    assert a == b and a.startswith("sha256:")


def test_registry_describes_epistemic_class_and_provenance():
    item = build_default_registry().describe()[0]
    assert item["operations"][0]["epistemicClass"] in {"calculation","heuristic","simulation","advisory"}
    assert item["provenance"]["donorCommit"]
```

- [ ] **Step 2: Run focused tests and verify RED**

Run: `/private/tmp/capt-lab-baseline-venv/bin/python -m pytest tests/capt_lab/test_lab_contracts.py tests/capt_lab/test_registry.py -q`
Expected: import/module failures because `capt_lab` does not exist.

- [ ] **Step 3: Implement canonical contracts/provenance/registry**

Use sorted-key UTF-8 JSON with compact separators and reject NaN/Infinity. Validate IDs against CAPT's identifier-safe subset, cap input serialized bytes, reject unknown fields, and make descriptor dictionaries immutable-by-construction copies.

Manifest entries must include the exact `28e7834982c859731636e733c53df9f84893f897` donor commit for Math/VSA/QIPC/Forge plus source SHA-256 digests from the design spec. `4InversionLabs/ForgeProof Commons/evaluation-rubric.json` is recorded as a local donor without fabricating a Git commit.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the Task 1 pytest command; expected all PASS.

- [ ] **Step 5: Run packaging import proof**

Build/install wheel in a disposable venv and assert `capt_lab.__file__` resolves from site-packages with empty `PYTHONPATH`.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml capt_lab tests/capt_lab/test_lab_contracts.py tests/capt_lab/test_registry.py
git commit -m "feat(lab): add governed engine registry contracts"
```

---

### Task 2: Deterministic Math engine

**Files:**
- Create: `capt_lab/engines/math_engine.py`
- Create: `tests/capt_lab/test_math_engine.py`
- Update: `capt_lab/registry.py`
- Update: `capt_lab/donors/manifest.json`

**Interfaces:**
- Consumes canonical `LabEngineRequest`.
- Produces `LabEngineResult` for `cyclotomic_summary` and `mcmillan_tc`; optional `materials_screen` remains explicitly heuristic.

- [ ] **Step 1: Write RED tests from donor behavior**

```python
def test_cyclotomic_summary_for_fifth_roots():
    out = run_math("cyclotomic_summary", {"conductor": 5})
    assert out.epistemic_class == "calculation"
    assert out.observation["degree"] == 4
    assert out.observation["unitRank"] == 1
    assert out.observation["torsionOrder"] == 10


def test_mcmillan_tc_rejects_singular_domain():
    with pytest.raises(LabInputError):
        run_math("mcmillan_tc", {"debyeK": 300.0, "lambda": 0.1, "muStar": 0.5})
```

Also add fixtures comparing accepted values against the donor Rust implementation/formula.

- [ ] **Step 2: Verify RED**

Run: `/private/tmp/capt-lab-baseline-venv/bin/python -m pytest tests/capt_lab/test_math_engine.py -q`

- [ ] **Step 3: Implement the smallest honest operations**

Port only the donor formulas needed by the exposed operations. Do not port placeholder class-group/dlog, protein-gradient, linear superconducting predictor, or Eliashberg stubs. Return limitations that name excluded/unvalidated routines.

- [ ] **Step 4: Cross-check donor crate**

Run in donor snapshot: `cargo test --all-features --quiet` and `cargo check --all-features --quiet`; expected 17 tests pass and check succeeds.

- [ ] **Step 5: Verify GREEN and commit**

```bash
/private/tmp/capt-lab-baseline-venv/bin/python -m pytest tests/capt_lab/test_math_engine.py -q
git add capt_lab/engines/math_engine.py capt_lab/registry.py capt_lab/donors/manifest.json tests/capt_lab/test_math_engine.py
git commit -m "feat(lab): restore bounded CAPTLang math engine"
```

---

### Task 3: Deterministic structural analogy and QIPC consensus

**Files:**
- Create: `capt_lab/engines/analogy.py`
- Create: `capt_lab/engines/consensus.py`
- Create: `tests/capt_lab/test_analogy.py`
- Create: `tests/capt_lab/test_consensus.py`
- Update: `capt_lab/registry.py`

**Interfaces:**
- `run_analogy(operation, input) -> LabEngineResult`
- `run_consensus(operation, input) -> LabEngineResult`

- [ ] **Step 1: Write RED determinism and bounds tests**

```python
def test_symbol_vectors_are_cross_process_deterministic(tmp_path):
    one = subprocess.check_output([sys.executable, "-c", SCRIPT], text=True)
    two = subprocess.check_output([sys.executable, "-c", SCRIPT], text=True)
    assert one == two


def test_consensus_never_claims_verification():
    out = run_consensus("aggregate_beliefs", {"beliefs":[0.2, 0.8, 0.7]})
    assert out.epistemic_class == "advisory"
    assert "verified" not in out.observation
```

Add size/count/finite-number rejection tests.

- [ ] **Step 2: Verify RED**

Run both test files; expected missing adapters.

- [ ] **Step 3: Implement hardened adapters**

For VSA, derive all pseudo-random vectors from `sha256(symbol.encode())` rather than Python `hash()`. Preserve structural mapping concepts without importing legacy authority/state.

For QIPC, port only bounded belief aggregation/entropy/confidence diagnostics needed by R1. No gossip network, no hard-coded truth threshold that changes CAPT state, and no network calls.

- [ ] **Step 4: Verify cross-process determinism and GREEN**

Run both focused suites under two separate interpreter processes.

- [ ] **Step 5: Commit**

```bash
git add capt_lab/engines/analogy.py capt_lab/engines/consensus.py capt_lab/registry.py tests/capt_lab/test_analogy.py tests/capt_lab/test_consensus.py
git commit -m "feat(lab): add deterministic analogy and consensus engines"
```

---

### Task 4: Bounded Forge/Invention advisory

**Files:**
- Create: `capt_lab/engines/forge.py`
- Create: `tests/capt_lab/test_forge.py`
- Update: `capt_lab/registry.py`

**Interfaces:**
- `analyze_repository(root: Path, limits: ForgeLimits) -> LabEngineResult`
- Operations: `repository_archaeology`, `gap_analysis`, `sigma_brief`, `forgeproof_score`.

- [ ] **Step 1: Write RED security tests**

Cover traversal, symlink escape, `.env`/private-key exclusion, byte/file/depth caps, binary exclusion, and read-only behavior. Create a fixture repo with a symlink pointing outside the root and assert it is reported as excluded rather than read.

- [ ] **Step 2: Write RED truthfulness tests**

Assert results contain no keys/phrases representing simulated prior art, patentability, novelty percentage, or fake reviewer consensus.

- [ ] **Step 3: Implement bounded read-only archaeology/gap/rubric logic**

Reuse donor concepts, not the old BaseModule runtime. Resolve canonical root once, use `lstat`/resolved containment checks, never follow escaping symlinks, redact candidate secret patterns, and summarize only bounded metadata/text excerpts.

- [ ] **Step 4: Verify GREEN and repository immutability**

Hash fixture tree before and after Forge invocation and assert identical digest.

- [ ] **Step 5: Commit**

```bash
git add capt_lab/engines/forge.py capt_lab/registry.py tests/capt_lab/test_forge.py
git commit -m "feat(lab): add bounded Forge advisory engine"
```

---

### Task 5: Governed RuntimeService Lab execution and evidence admission

**Files:**
- Create: `tests/capt_lab/test_runtime_advisory.py`
- Modify: `desktop/m1_command_service.py`
- Modify: `desktop/capt_runtime_service.py`
- Reuse: `capt_runtime/services.py`, `capt_runtime/verification.py` without schema changes unless a failing frozen-contract test proves necessary.

**Interfaces:**
- Query `lab_engines` returns `LabEngineRegistry.describe()`.
- Command `run_lab_engine_advisory` returns receipt with `missionId`, `taskId`, `driverRunId`, `claimId`, `evidenceId`, `artifactPath`, `artifactDigest`, `requestDigest`, `epistemicClass`, `verificationId=None`, `promotionState="proposed"`.

- [ ] **Step 1: Write RED authority tests**

```python
def test_success_records_observation_without_promotion(runtime):
    receipt = runtime.run_lab(...)
    assert state("driverrun-" + receipt["driverRunId"])["state"] == "completed"
    claim = state("claim-" + receipt["claimId"])
    assert claim["kind"] == "observation"
    assert claim["promotionState"] == "proposed"
    assert claim["verificationId"] is None
    assert state("task-" + receipt["taskId"])["state"] != "succeeded"
```

Add tests for mission/task mismatch, terminal task, unknown engine/op, engine exception, artifact tamper, replay, and idempotency collision.

- [ ] **Step 2: Verify RED against unchanged command service**

Expected: unknown `lab_engines`/`run_lab_engine_advisory` operations.

- [ ] **Step 3: Implement query and prepared execution path**

The runner must validate before DriverRun creation, create/transition DriverRun through CAPT services, execute one registry adapter, write canonical result bytes beneath a bounded Lab staging root, re-read/hash exact bytes, propose an `observation` Claim, build existing `artifact_hash` evidence, and attach it with `record_evidence`.

Use durable command claim/complete semantics already used by the provider path so exact replay returns the prior receipt without adapter execution.

- [ ] **Step 4: Prove no epistemic promotion**

Inspect ledger events and assert the command adds no `ClaimVerified`, `ClaimGuardDecided`, task-success, or mission-complete event.

- [ ] **Step 5: Run RuntimeService and full Python regression**

```bash
/private/tmp/capt-lab-baseline-venv/bin/python -m pytest tests/capt_lab/test_runtime_advisory.py -q
/private/tmp/capt-lab-baseline-venv/bin/python -m pytest -q
```

Expected full result remains at least the frozen-base 884 passing tests plus new Lab tests, with no new failures.

- [ ] **Step 6: Commit**

```bash
git add desktop/m1_command_service.py desktop/capt_runtime_service.py tests/capt_lab/test_runtime_advisory.py
git commit -m "feat(lab): govern specialist advisories through RuntimeService"
```

---

### Task 6: Native Labs operator surface

**Files:**
- Create: `capt_ui/surfaces/desktop_swift/Sources/CAPTCoreDesktop/CAPTLabModels.swift`
- Create: `capt_ui/surfaces/desktop_swift/Sources/CAPTNativeMac/Views/LabsView.swift`
- Create: `capt_ui/surfaces/desktop_swift/Tests/CAPTCoreDesktopTests/CAPTLabProjectionTests.swift`
- Modify: `CAPTBackgroundRuntime.swift`, `CAPTOperatorStore.swift`, `SidebarView.swift`, `ContentView.swift`.

**Interfaces:**
- Runtime actor: `labEngines() -> [CAPTLabEngineSnapshot]`, `runLabAdvisory(...) -> CAPTLabRunReceipt`.
- Store publishes registry, selected engine/op, last receipt/error.

- [ ] **Step 1: Write RED projection tests**

Assert epistemic class, limitations, donor commit/digests, availability, and proposed/unverified receipt state survive JSON projection.

- [ ] **Step 2: Implement typed projections and runtime actor methods**

No direct engine imports/execution in Swift; only `lab_engines` query and `run_lab_engine_advisory` command.

- [ ] **Step 3: Build Labs view**

Show engine cards, operation picker, bounded JSON/form input, active mission/task binding, epistemic badge, limitations/provenance, and result IDs/digests. Render `proposed`/`verificationId=nil` as `UNVERIFIED`, never as success/verified.

- [ ] **Step 4: Run Swift tests/build**

```bash
cd capt_ui/surfaces/desktop_swift
swift test
swift build --product CAPTNativeMac
```

- [ ] **Step 5: Commit**

```bash
git add capt_ui/surfaces/desktop_swift
git commit -m "feat(mac): add governed Inversion Labs engine surface"
```

---

### Task 7: Installed-artifact and live Lab dogfood

**Files:**
- Modify: native README/status docs.
- Create: `reports/lab/INVERSION_LABS_R1_DOGFOOD.md`
- Create: `reports/lab/INVERSION_LABS_R1_DOGFOOD.json`

**Interfaces:**
- Evidence report records exact source SHA, wheel hash, signed-app identity, donor manifest digest, test counts, and one real receipt per R1 engine family.

- [ ] **Step 1: Run exact full regressions**

Use a clean package-installed Python venv and Swift normal/live tests. Record counts exactly; never copy earlier counts if they changed.

- [ ] **Step 2: Build/install exact Lab wheel**

Verify `capt_lab`, `capt_runtime`, and `capt_ui` import from site-packages with `PYTHONPATH` empty and `PYTHONNOUSERSITE=1`. Record SHA-256.

- [ ] **Step 3: Dogfood each engine through authenticated RuntimeService**

Run Math, Analogy, Consensus, and Forge on bounded non-destructive inputs. For each receipt prove completed DriverRun, proposed observation Claim, evidence digest, no verification/promotion, and replay idempotency.

- [ ] **Step 4: Dogfood signed native Labs view**

Build/sign with stable `com.inversionlabs.capt` identity, open Labs, run at least one advisory from the UI, and verify the same ledger receipt read-only afterward.

- [ ] **Step 5: Write evidence report and commit**

```bash
git add reports/lab capt_ui/surfaces/desktop_swift/README.md
git commit -m "test(lab): capture R1 installed dogfood evidence"
```

---

### Task 8: Final reconciliation, provenance lock, and PR

**Files:**
- Update: `capt_lab/donors/manifest.json`
- Update: spec/status only if implementation evidence requires clarification.
- Create: `docs/lab/INVERSION_LABS_R1_FUNCTIONALITY.md`

**Interfaces:**
- Final classification: `INVERSION_LABS_R1_DOGFOOD_READY`, `READY_WITH_BOUNDED_LIMITS`, `NOT_READY`, or `BLOCKED`.

- [ ] **Step 1: Run final diff/secret/path scans**

Check `git diff --check`, tracked secrets, absolute developer paths in shipped code/artifacts, donor-license files, and generated/build directories accidentally staged.

- [ ] **Step 2: Re-run exact full Python + Swift regressions from clean artifacts**

No completion claim without fresh outputs.

- [ ] **Step 3: Reconcile spec acceptance gates one by one**

The functionality doc must state PASS/FAIL/BLOCKED for every gate and cite exact test/report evidence. Any failed authority, replay, secret, artifact-integrity, or promotion gate forces `NOT_READY`/`BLOCKED`.

- [ ] **Step 4: Commit final reconciliation**

```bash
git add capt_lab docs/lab reports/lab
git commit -m "docs(lab): reconcile R1 dogfood candidate"
```

- [ ] **Step 5: Push Lab branch and open a stacked PR**

Base the PR on the exact native/core branch lineage required to preserve `5f291777...`; do not merge into main during this workflow. Record local HEAD == remote HEAD and GitHub mergeability/status.
