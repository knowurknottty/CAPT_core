# CAPT Core v0.5 API Reference

- **Version:** `0.5.0`
- **Stability policy:** `docs/PUBLIC_API_STABILITY.md`
- **Installed command:** `capt`

CAPT has multiple deliberate package-level APIs. `capt_solo.api` remains the
stable convenience facade for the full local runtime; it is not the only valid
public import path.

## Stable Surfaces

### Runtime facade

```python
from capt_solo.api import (
    MemoryEngine,
    Memory,
    SearchAdapter,
    SearchHit,
    CTPRuntime,
    Receipt,
    KHSB,
    Message,
    health,
)
```

The facade preserves the existing Memory, CTP, KHSB, lifecycle, configuration,
and error exports. Runtime constructors may create local state only under the
configured `CAPT_SOLO_HOME`.

### ContextPack v1

```python
from capt_solo.contextpack import (
    ContextPack,
    Mission,
    MissionIntent,
    Assumption,
    RecordRef,
    TokenBudget,
    build_context_pack,
    build_from_context_result,
    canonical_json,
    render_handoff,
    validate_context_pack,
)
```

ContextPack v1 is deterministic for equivalent inputs. Unknown semantic fields
are rejected by default. Protected-fact, assumption-review, fidelity, and token
budget failures block generation rather than silently weakening the pack.

### Transactions

```python
from capt_solo.ctp import CTPRuntime, Receipt
```

`CTPRuntime` provides:

- `begin(correlation_id=None, idempotency_key=None, meta=None)`;
- `validate(tx_id, result)`;
- `note(tx_id, note)`;
- `commit(tx_id) -> Receipt`;
- `abort(tx_id) -> Receipt`;
- `get_receipt(tx_id)`;
- `recover()`;
- `audit_trail(tx_id)`;
- `integrity_check()`;
- `close()`.

The journal is append-only JSONL. Callers can supply an explicit `journal_dir`
or `journal_path`.

### Memory

```python
from capt_solo.memory import MemoryEngine, Memory
```

The stable MemoryEngine surface includes local store/get/update/delete/search,
export/import, backup/restore, integrity checking, migration, and explicit
close. The persisted SQLite schema is versioned separately from Python API
stability.

### KHSB and Plugin

```python
from capt_solo.khsb import KHSB, Message
from capt_solo.plugin import get_plugin
```

KHSB is in-process and networking-free. The Hermes plugin manifest and bundled
skills are package data and are verified in wheel and sdist artifacts.

## Provisional Surfaces

### Evidence

```python
from capt_solo.evidence import (
    EvidenceRecord,
    EvidenceClaim,
    EvidenceSource,
    EvidenceClass,
    EvidenceStatus,
    EvidenceScope,
    InvalidationEvent,
    EvidenceReuseEngine,
    ProjectWorkspace,
    MissionCheckpoint,
)
```

`capt_solo.evidence.EvidenceRecord` is the canonical evidence record for new
public evidence workflows under ADR-0009. Existing Foundry, Knowledge,
Continuity, Verification, and Memory evidence-like records remain supported
specialized or compatibility types.

### Verified State Identity

```python
from capt_solo.verification import (
    VerifiedStateIdentity,
    VerificationScope,
    VerificationRecord,
    VerificationEvidence,
    VerificationPolicy,
    VerificationStore,
    VerificationEngine,
    build_vsi,
    diff_vsi,
    vsi_equivalent,
)
```

VSI binds applicability to repository, branch, HEAD, scoped file hashes,
dependency state, runtime, operating environment, command, and verification
scope. Conversation age is not part of equivalence.

### Workspace

```python
from capt_solo.workspace import workspace_status, validate_workspace, run_command
```

Workspace operations read repository authority as untrusted data. Writes occur
only for explicit checkpoint/archive actions. Repository-only commands require a
source checkout containing `architecture/` and the governed root documents.

### Foundry and Governance

```python
from capt_solo.foundry import (
    ProofEngine,
    ProofRequirement,
    CapabilityRegistry,
    ClaimGuard,
    SkillFoundry,
    ValidationHarness,
    KnowledgeBubbleRuntime,
    Governance,
    SkillCurator,
    WorkflowProofEngine,
)
```

Foundry's proof, capability, skill, bubble, workflow, and governance records are
specialized subsystem contracts. They are not aliases for canonical Evidence.

### Ontology, Knowledge, Continuity, and Execution

The following packages are shipped and public at provisional stability:

```text
capt_solo.ontology
capt_solo.knowledge
capt_solo.continuity
capt_solo.execution
```

Continuity remains CVE v0.2 policy evaluation. It does not execute production
drills. Execution capability boundaries default-deny unauthorized side effects.

## Experimental Surfaces

```text
capt_solo.engines
capt_solo.learning
capt_solo.research
capt_solo.pulse
```

These packages ship because real implementations depend on or demonstrate them,
but they are not stable verification-kernel APIs. PULSE is disabled by default
and performs no network activity on import.

## Installed CLI

```text
capt doctor
capt memory ...
capt session ...
capt procedure ...
capt prospective ...
capt retrieval ...
capt foundry ...
capt canon ...
capt verify ...
capt evidence ...
capt continuity ...
capt mission ...
capt selfmod ...
capt workspace ...
capt architecture ...
capt release validate
```

Use `capt <group> --help` for arguments. `capt doctor` is read-only and checks
installed profile imports, package data, and the default network boundary
without creating runtime state.

## Record Terminology

- **check:** one observation-producing verifier execution;
- **evidence:** observation plus provenance;
- **evaluation:** policy application to evidence for a subject state;
- **attestation:** portable result of evaluation;
- **receipt:** integrity-bound record that an operation, evaluation, or governed
  decision occurred.

These terms do not collapse current internal record classes in v0.5.

## Errors

The stable runtime error hierarchy is exported from `capt_solo.core.errors`:

```text
CaptSoloError
MemoryError_
TransactionError
IdempotencyError
BusError
IntegrityError
ConfigurationError
MigrationBackupError
```

CLI commands return nonzero exit status and write diagnostics to stderr on
failure. Hermes tools return structured error objects rather than leaking
exceptions across the plugin boundary.
