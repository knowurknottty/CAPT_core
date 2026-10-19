# Quantum Leap v3 — read-only experimental claim probes

Source provenance: `knowurknottty/CAPT_core` at `e28b665`. This research area is separate from CAPT's installed runtime. It does **not** mutate authority, issue approval, verify natural-language entailment, or promote claims.

The `beliefprobe.py` verifier evaluates eight manually encoded predicate kinds against immutable Git objects. A `WITHIN` verdict only says that the encoded predicate held at the pin. Output always has `semantic_entailment=NOT_ASSESSED` and `promotion_eligible=false`.

## Inputs and results

- `claims_v3_original.json`: all 52 maintainer-supplied v3 claims, unchanged.
- `spotcheck_claims.json`: earlier eight-example smoke test.
- `phase2_audit.py`: deterministic three-pin comparison, bounded first-parent history, predicate-mutation controls, D_proxy accounting.
- `phase2_results.json`: full output with source digest and Git SHAs.
- `phase2_report.md`: limitations, audit verdicts and risk boundaries.
- `test_beliefprobe.py`: twelve real temporary-Git fixtures.

Run regression tests:

```zsh
python3 -I research/quantum_leap_v3/test_beliefprobe.py
```

Generate an independent history audit under an unused output filename:

```zsh
python3 -I research/quantum_leap_v3/phase2_audit.py . research/quantum_leap_v3/claims_v3_original.json /tmp/quantum-leap-audit-new.json
```

The historical run can be slow. The audit refuses to overwrite its output. Use the exact source pin recorded in output; do not substitute the running runtime's assumed source identity. No automation or claim-promotion integration is authorized by this experiment.

**Certainty:** `D_proxy` is an obligation-counting proxy, *not* measured semantic truth or a production Ratchet.
