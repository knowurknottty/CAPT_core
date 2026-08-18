# CAPT-UPG-009 — Isolated Workspace + Governed Artifact Promotion

- **Campaign ID:** `CAPT-UPG-009`
- **Issue:** #67
- **PR:** #68
- **Branch:** `upgrade/capt-upg-009-workspace-promotion`
- **Current predecessor:** repaired `CAPT-UPG-008`
- **Disposition:** `IMPLEMENTED_VERIFIED_READY_FOR_OWNER_REVIEW`

## Corrected authoritative lifecycle

The earlier helper-level promotion model was rejected because filesystem copying was not itself an authoritative CAPT transaction. The corrected lifecycle is:

`staged candidate -> PREPARE -> verify bound evidence -> AUTHORIZE -> atomic ADOPT | DISCARD`

Authority boundaries:

- `ArtifactPromotionAggregate` owns the durable promotion transaction.
- `GovernedRuntimeService` is the only authoritative mutation path.
- Claim verification and ClaimGuard promotion remain distinct from filesystem adoption authority.
- Authorization binds promotion ID, candidate/workspace identity, source path, canonical destination path, exact content digest, claim ID, verification ID, and evidence ID.
- Adoption revalidates the current claim verification/evidence binding and staged digest before the filesystem effect.
- Atomic destination replacement has deterministic recovery when the exact authorized bytes are already present after process death.
- Legacy direct promotion helpers cannot bypass the RuntimeService transaction.

## Contract integration closure

The authoritative EventEnvelope contract now explicitly supports:

- `artifact_promotion-*` stream IDs;
- `ArtifactPromotionPrepared`;
- `ArtifactPromotionAuthorized`;
- `ArtifactPromotionAdopted`;
- `ArtifactPromotionDiscarded`;
- typed `ArtifactPromotionState` and `ArtifactAdoptionReceipt` payloads.

Python and TypeScript generated bindings are regenerated from the normative JSON Schema source. Cross-language fixture discovery is symmetric and includes a valid ArtifactPromotion EventEnvelope parity case.

## Verification

Fresh verification on the repaired UPG-008 ancestry:

```bash
python contracts/tools/check_drift.py
python -m pytest -q
```

Observed result before commit of the identical tree:

```text
DRIFT CHECK: OK (11 generated files match the schema source)
950 passed, 13 skipped, 12 deselected
```

The exact commit SHA is recorded in the PR/issue after commit creation. No claim is made beyond the tested non-slow suite and contract drift gate.
