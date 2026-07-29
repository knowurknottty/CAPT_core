# CVE v0.2 Operational Continuity Runtime

CAPT Solo implements a local, inspectable CVE evidence evaluator. It is not a
claim that CAPT Solo or another repository is constitutionally certified.

The policy is [architecture/cve/continuity-v0.2.yaml](../architecture/cve/continuity-v0.2.yaml).
It has nine clauses, four continuity tiers (`C0` through `C3`), and defaults to
blocking rather than guessing when evidence is absent, invalid, expired, or
unknown.

## Runtime boundary

`capt_solo.continuity` accepts JSON evidence packs, computes canonical SHA-256
digests, evaluates role separation, evidence freshness/invalidation, source
concentration, and reversible-handoff requirements. It writes no data, makes
no network call, and contains no production connector or signing key support.

`capt continuity plan-drill` emits a sandbox-only plan with `NOT_RUN`; it does
not execute a recovery drill. `production` is rejected.

## Commands

```bash
python3 capt_cli.py continuity validate-policy
python3 capt_cli.py continuity validate-pack continuity_examples/capt-solo-memory-c1.json
python3 capt_cli.py --json continuity evaluate continuity_examples/capt-solo-memory-c1.json
python3 capt_cli.py --json continuity plan-drill continuity_examples/capt-solo-memory-c1.json
```

An evaluation that returns `BLOCK` exits with code 2. A receipt is only a
digest-bound record; it is not a signature or an approval.

## Traceability and limits

The runtime covers CVE v0.2 pack validation, tier/role gates, evidence status,
receipt verification, proof-graph-shaped output, concentration warnings, and
safe drill planning. It deliberately does not claim external PULSE, Hyper-MCP,
Android, CAPT-RYS, or bioCAPT evidence: those components are outside this
checkout and require their own packs and real evidence.

| CVE clauses | Runtime mechanism |
|---|---|
| 01, 03, 05 | Local JSON packs, secret screening, explicit role records |
| 02, 08 | Canonical policy parsing, deterministic digests, receipt verification |
| 04 | No telemetry, network I/O, or persistence in the evaluator |
| 06, 09 | Evidence expiry/invalidation and sandbox-only reversible-drill planning |
| 07 | Distinct operator/reviewer identities and concentration warnings |
