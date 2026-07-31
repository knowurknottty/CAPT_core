# RECURSION_PASS_3_EVIDENCE_CHAIN — Independent Evidence-Chain Audit

Auditor: Independent (Pass 3). Date: 2026-07-30. Candidate SHA: `7b9bcf4`.
Method: re-derive every conclusion from code/tests/runtime/artifacts/commit
history. Prior reports treated as hypotheses, not evidence. No repo modified.

## Capability evidence chain (Requirement → Implementation → Tests → Runtime →
Package → Docs → Claim → Evidence)

| Capability | Impl location | Tests | Runtime (wheel) | Package | Docs claim | Public claim | Chain status |
|---|---|---|---|---|---|---|---|
| Memory | `memory/engine.py` MemoryEngine | suite | PASS (store/get/ns/export) | wheel | README L20 | "local SQLite storage" | ✅ INTACT |
| CTP | `ctp/journal.py` CTPRuntime | suite | PASS (begin/commit/get_receipt) | wheel | README | "append-only receipts" | ✅ INTACT |
| CapabilityRegistry | `foundry/registry.py` | suite | PASS (register/get) | wheel | PUBLIC_ARCH | "explicit states" | ✅ INTACT |
| ProofEngine | `foundry/proof.py` | suite | PASS (add_evidence/evaluate+scope) | wheel | README | "proof aggregation" | ✅ INTACT |
| ClaimGuard | `foundry/claimguard.py` | suite | PASS (ctor) | wheel | README | "prevents unsupported claims" | ✅ INTACT |
| Governance | `foundry/governance.py` | suite | PASS (ctor) | wheel | README | "governance" | ✅ INTACT |
| Knowledge Bubbles | `foundry/bubble.py` | suite | PASS (ctor) | wheel | README | "skill bubbles" | ✅ INTACT |
| ContextPack v1 | `contextpack/` | **12 tests pass** | exists, callable | wheel | README L21 | "deterministic ContextPack v1" | ✅ INTACT (via tests) |
| VSI | `verification/identity.py` VerifiedStateIdentity | **14 tests pass** | PASS (identity_tuple) | wheel | README L18 | "binds verification to repo state" | ✅ INTACT |
| Evidence | `evidence/` EvidenceRecord | suite | PASS (real objects) | wheel | README | "evidence with provenance" | ✅ INTACT |
| CLI | `capt_cli.py` | suite | PASS (all subcommands) | wheel | README | "capt CLI" | ✅ INTACT |
| No-network import | pulse.py lazy | suite | PASS (socket-deny) | wheel | "local-first" | ✅ INTACT |
| Zero Hermes import | plugin/__init__.py inbound only | suite | PASS (grep) | wheel | "no harness dependency" | ✅ INTACT |
| Release validator | `release_validation.py` | suite | **FAILS** (see F1) | wheel | EXACT_SHA doc | "validator passes" | ❌ BROKEN (F1) |

## Circular-reference detection
- EXACT_SHA_RELEASE_VALIDATION.md claimed `release validate` PASS. This audit
  re-ran it and found FAIL. The prior claim depended on non-final mode output
  or misreading — NOT on re-derivation. No report→report→report loop found
  otherwise; most docs cite code/tests. The convergence docs correctly cite
  commit SHAs and test output.
- QUAD_RECURSION_HANDOFF lists authoritative vs superseded reports — no
  circular citation detected among authoritative set.

## Package audit (wheel vs sdist vs source)
- wheel `capt_solo-0.5.0-py3-none-any.whl` installs; 20 packages import.
- sdist installs; no-network import proven.
- `capt_solo.components` IS in wheel (ATE recovered) but NOT in manifest
  declared list → F1.
- LICENSE in wheel (dist-info/licenses/). Docs NOT in wheel (sdist only) — normal.

## Reproducibility
- 715 tests: reproduced this session (post-OD4) — not inherited.
- Artifact hashes recorded in release_evidence/*.json.
- bandit/semgrep/pip-audit: NOT run at SHA (owner-gated, runs in CI on push).

## Findings

### F1 — release validator FAILS on package_inventory [HIGH / BLOCKER-class]
- Evidence: `capt_cli release validate` → `public_api.package_inventory: fail`.
  declared=['capt_solo',...] (18 pkgs, NO components); source=['capt_solo',
  'capt_solo.components',...] (19 pkgs).
- Root cause: OD-4 recovered `capt_solo.components` (ATE) but did NOT update
  `docs/release/PUBLIC_API_MANIFEST_V0.5.json` declared package list.
- doc 07 machine-enforced failure: "an advertised package is missing" → release
  MUST fail. This is a REAL release blocker.
- Prior reports BASELINE_REVALIDATION + EXACT_SHA_RELEASE_VALIDATION stated the
  validator passes — CONTRADICTED by this independent re-run. Those reports were
  WRONG (ran non-final mode, which passes on UNFROZEN, or misread output).
- Disposition: MUST FIX before freeze. Add `capt_solo.components` to manifest
  declared stable list. One-line change. Owner decision: approve the manifest
  edit (it is a documentation/metadata correction, not code).

### F2 — public API complexity vs simplified claims [MEDIUM]
- Evidence: EvidenceRecord requires EvidenceClaim+EvidenceSource; ContextPack
  requires Mission/Assumption/ProtectedFact objects; build_vsi needs
  VerificationScope+command. README presents these as simple capabilities.
- Chain INTACT (tests cover all) but a new user cannot construct them from
  README alone. Documentation-clarity gap, not a broken chain.
- Disposition: MEDIUM. Recommend Pass 4 add a "constructing X" snippet to docs.
  Not a release blocker (functionality exists + tested).

### F3 — VSI/ContextPack/Evidence "missing" in audit script [FALSE_POSITIVE]
- Initial audit script imported wrong paths / wrong kwargs. Re-verified: all
  three exist, are tested (12+14 tests), and run from wheel. No defect.

### F4 — docs not in wheel [LOW / ACCEPTED]
- Standard Python packaging. No claim asserts docs ship in wheel. Accepted.

## Final question
Can the entire release narrative be reconstructed from objective repository
evidence without trusting prior reports?
- YES for: architecture capabilities (code+tests+wheel verify each).
- YES for: no-network/no-Hermes (socket-deny + grep).
- NO for: "release validator passes" — prior reports asserted this; independent
  re-run shows it FAILS (F1). The narrative was WRONG on this point.
- Missing link: manifest declared-packages list must include components before
  the validator claim is true.

## Verdict
One HIGH finding (F1) breaks the release claim "validator passes." It is a
one-line manifest correction (add capt_solo.components). All capability chains
otherwise terminate in code/tests/runtime. Prior reports' validator-PASS claim
is RETRACTED by this audit.
