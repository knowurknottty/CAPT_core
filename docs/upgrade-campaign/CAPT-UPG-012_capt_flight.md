# CAPT-UPG-012: `.capt-flight` Forensic Reproducibility Bundle

- **Campaign ID**: `CAPT-UPG-012`
- **Issue**: #75
- **Branch**: `upgrade/capt-upg-012-capt-flight`
- **PR**: #76
- **Implementation head at evidence creation**: `6181e06f14e1603332782e7c794f22808939f5cc`
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

## Tests added

`tests/capt_runtime/test_flight_recorder.py` contains three discriminating tests covering:

1. deterministic manifest identity, recursive secret redaction, and read-only EventStore behavior;
2. member tamper detection;
3. unmanifested-member rejection.

## Compatibility review

The implementation was corrected to preserve the repository's declared Python `>=3.8` contract by using `typing.Union` rather than PEP 604 union syntax.

## Verification boundary

A GitHub Actions lookup for exact head `6181e06f14e1603332782e7c794f22808939f5cc` returned **no workflow runs**. The connected execution environment also cannot clone/run the repository because outbound container DNS/network access is unavailable.

Therefore no pytest PASS is claimed here. The current evidence class is:

`SOURCE_IMPLEMENTED / TESTS_AUTHORED / EXACT_HEAD_EXECUTION_NOT_OBSERVED`

This item must remain draft/pending verification until an executable environment runs at least:

```bash
pytest tests/capt_runtime/test_flight_recorder.py
```

and, before owner-ready integration, the relevant runtime/full-suite regression gates.
