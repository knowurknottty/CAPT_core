# CAPT-UPG-012: `.capt-flight` Forensic Reproducibility Bundle

- **Campaign ID**: `CAPT-UPG-012`
- **Issue**: #75
- **PR**: #76
- **Rebuilt base**: corrected CAPT-UPG-011 @ `c27db815fda9f133607db08e946ed7548877f9c7`
- **Disposition**: `IMPLEMENTED_PENDING_CI_VERIFICATION`

## Scope implemented

`capt_runtime/flight_recorder.py` adds a read-only forensic exporter that:

- verifies the authoritative EventStore chain before export;
- records the selected EventStore event slice and aggregate projections;
- accepts optional checkpoint, runtime metadata, and artifact references;
- recursively redacts default and caller-specified secret fields/values;
- emits deterministic JSON payloads and fixed-metadata ZIP members;
- records a content digest and size for every bundled member;
- records an explicit `forensic_projection_only` authority classification;
- independently verifies manifest/member integrity;
- rejects missing, tampered, or unmanifested members.

The bundle is explicitly **not** RuntimeService/EventStore authority, a verification receipt, a ClaimGuard decision, or replay/dispatch authorization.

## Tests authored

`tests/capt_runtime/test_flight_recorder.py` covers deterministic manifest identity, recursive secret redaction, read-only EventStore behavior, member tamper detection, and unmanifested-member rejection.

## Verification boundary

The prior implementation was rebuilt scope-only on the corrected UPG-011 substrate to remove stale inherited Cohort/steering code. No pytest PASS is claimed here because the connected execution environment cannot run the repository and exact-head GitHub Actions must be observed separately.

Required:

```bash
pytest tests/capt_runtime/test_flight_recorder.py
pytest tests/capt_runtime/test_cohort_durability.py tests/capt_runtime/test_operator_steering_durable.py
pytest
```
