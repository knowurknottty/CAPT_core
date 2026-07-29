# CVE v0.2 Phase II — Native Continuity Integration

## Architecture review

Phase I correctly kept the evaluator isolated, but it accepted a flat evidence
list and made callers assemble provenance manually. It also emitted a receipt
timestamp from wall-clock time, so reproducibility required an undocumented
caller convention. Phase II removes those coupling points without changing the
nine-clause policy or giving CAPT components knowledge of CVE.

The remaining deliberate limits are: no signature authority, no production
recovery, no cross-process locking, and no automatic durable receipt chain.
Receipt persistence is explicit because a hidden write would violate the local
workspace boundary. The chain is thread-safe within a process; coordinated
multi-process writers remain a future, separately designed concern.

## Provider contract

`capt_solo.evidence.providers.EvidenceProvider` is read-only and policy-neutral:
`status()`, `digest()`, `timestamp()`, `version()`, and `evidence()`.
`OperationalEvidence` has a stable id, type, timestamp, digest, dependencies,
origin, status, confidence, and non-secret detail. Providers do not import
CVE. The Phase II adapters are `MissionProvider`, `MemoryProvider`, and
`StaticProvider` (for Learning/Research until they expose their own runtime
facts).

Memory exposes `MemoryEngine.continuity_status()` rather than its database or
content. It reports integrity, schema version, metadata-only state digest,
retention/lifecycle summaries, and restore capability. Mission checkpoints
append digest-bound events in their existing `.capt/checkpoints/` boundary.

## Evidence graph and receipt chain

`EvidenceGraph` sorts nodes by id, rejects duplicates, missing dependencies,
cycles, invalid timestamps, and out-of-range confidence. Graph snapshots are
canonical JSON plus SHA-256 digest. `ReceiptChain` is explicit, local JSONL:
each entry contains the preceding receipt digest and its own chain digest.

Evaluation accepts both Phase I external packs and packs built from providers.
BLOCK results include CVE clause IDs, supporting/missing evidence, graph path,
remediation, and confidence. Future evidence relative to the supplied
evaluation clock blocks as clock skew. Supplying `now` makes output fully
repeatable; provider-built pack timestamps derive from the evidence snapshot.

## Migration guide

Existing Phase I packs remain valid; no persisted schema changes and no data
migration are required. To adopt providers:

```bash
python3 capt_cli.py --json continuity collect \
  --roles '[{"role":"operator","identity":"op"},{"role":"reviewer","identity":"review"}]' \
  --claims '[{"claim_id":"local","statement":"local runtime evidence"}]' \
  --include-memory --output /tmp/continuity-pack.json
python3 capt_cli.py --json continuity evaluate /tmp/continuity-pack.json
```

The output path is explicit. To persist an evaluation receipt, write its JSON
to a local file and use `continuity receipt-append --chain <local-jsonl>`.
Neither command contacts a service, executes a drill, or writes outside the
chosen output / existing `.capt` checkpoint boundary.

## Readiness assessment

Ready for local provider-backed continuity evaluation, explanation, and
in-process append-only receipt chains. Not ready to certify external CAPT
repositories or to claim multi-process receipt serialization, production
recovery, cryptographic signing, or automated provider coverage for Learning
and Research.
