# EVIDENCE_TRACEABILITY_MATRIX — Pass 3

Candidate: `7b9bcf4`. Each row is an independent re-derivation (code/test/runtime/
artifact), not a report citation. ✅ = chain terminates in objective evidence.
❌ = broken link found this audit.

| Req (Treasure Chest / public claim) | Implementation | Test evidence | Runtime (wheel) | Package artifact | Public doc | Public claim | Link |
|---|---|---|---|---|---|---|---|
| Memory namespaces | `memory/engine.py` MemoryEngine.store/get | suite | PASS | wheel | README L20 | "local SQLite, namespaces" | ✅ |
| Append-only transactions | `ctp/journal.py` CTPRuntime | suite | PASS | wheel | README | "CTP receipts" | ✅ |
| Capability states | `foundry/registry.py` | suite | PASS | wheel | PUBLIC_ARCH | "explicit states" | ✅ |
| Proof aggregation | `foundry/proof.py` ProofEngine | suite | PASS | wheel | README | "proof engine" | ✅ |
| ClaimGuard | `foundry/claimguard.py` | suite | PASS | wheel | README | "prevents unsupported claims" | ✅ |
| Governance | `foundry/governance.py` | suite | PASS | wheel | README | "governance" | ✅ |
| Skill bubbles | `foundry/bubble.py` | suite | PASS | wheel | README | "bubbles" | ✅ |
| Deterministic ContextPack | `contextpack/` | 12 tests | exists+callable | wheel | README L21 | "ContextPack v1" | ✅ |
| VSI | `verification/identity.py` | 14 tests | PASS (identity_tuple) | wheel | README L18 | "binds verification to repo state" | ✅ |
| Evidence provenance | `evidence/` EvidenceRecord | suite | PASS | wheel | README | "evidence w/ provenance" | ✅ |
| CLI surface | `capt_cli.py` | suite | PASS (all subcmds) | wheel | README | "capt CLI" | ✅ |
| Local-first / no network | `pulse.py` lazy import | suite | PASS (socket-deny) | wheel | "local-first" | ✅ |
| No Hermes dependency | plugin inbound-only | suite | PASS (grep) | wheel | "no harness dep" | ✅ |
| ATE security feature | `components/anti_token_extraction.py` | 575-line test (skippable) | imports, degrades | wheel | ANTI_TOKEN_EXTRACTION.md | "optional ATE" | ✅ |
| Release validator passes | `release_validation.py` | suite | **FAIL** (package_inventory) | wheel | EXACT_SHA doc (wrong) | "validator PASS" | ❌ F1 |
| LICENSE shipped | LICENSE file | dist test | in wheel (dist-info/licenses) | wheel | README "See LICENSE" | ✅ |
| Version 0.5.0 consistent | pyproject + __init__ + manifest | dist test | 0.5.0 | wheel | all docs | ✅ |

## Broken links
- **F1**: "release validator passes" claim → implementation `release_validation.py`
  exists and runs, but `public_api.package_inventory` check FAILS because the
  manifest declared-package list omits `capt_solo.components` (recovered in
  OD-4, manifest not updated). The claim is FALSE until the manifest is fixed.
  This is the ONLY broken link. All other 18 chains are intact.

## Conclusion
18/19 capability chains terminate in objective evidence. 1 broken link (F1) is
a metadata/manifest defect, not a code defect. Fix: add `capt_solo.components`
to `docs/release/PUBLIC_API_MANIFEST_V0.5.json` declared stable list.
