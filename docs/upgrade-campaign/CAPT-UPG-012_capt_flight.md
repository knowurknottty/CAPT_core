# CAPT-UPG-012 — `.capt-flight` Forensic Reproducibility Bundle

- **Campaign ID:** `CAPT-UPG-012`
- **Issue:** #75
- **PR:** #76
- **Base:** verified CAPT-UPG-011 @ `ca5ae5eda8fb8103f61e30713dc9148244d7f21a`
- **Disposition:** `IMPLEMENTED_VERIFIED_READY_FOR_OWNER_REVIEW`

## Scope

`capt_runtime/flight_recorder.py` provides a read-only forensic/support exporter that:

- verifies the authoritative EventStore chain before export;
- captures a selected EventStore event slice and aggregate projections;
- accepts optional checkpoint, runtime metadata, and artifact references;
- recursively redacts default and caller-specified secret fields/values;
- emits deterministic canonical JSON and fixed-metadata ZIP members;
- records content digest and size for every manifest member;
- declares `forensic_projection_only` authority semantics;
- independently verifies manifest/member integrity;
- rejects missing, modified, or unmanifested archive members.

A `.capt-flight` bundle is **not** RuntimeService/EventStore authority, a verification result, a ClaimGuard decision, a capability grant, or replay/dispatch authorization.

## Verification

Feature tests:

```bash
python -m pytest -q tests/capt_runtime/test_flight_recorder.py
```

The branch is scope-only on the verified UPG-011 substrate. Exact-commit full-suite verification is recorded on PR #76 after this evidence update; no claim extends to tests excluded by the repository's `slow` marker policy.
