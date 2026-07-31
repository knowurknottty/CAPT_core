# CAPT Core v0.5 — Release Security Report

Generated: 2026-07-30. Candidate SHA: `7b9bcf422c69d3afbbe600d64239c6dd8c3cea71`
(prior to Phase A blocker correction; this report documents the security
posture of the converged candidate. SHA updates after the correction commit.)

## Scope
This report covers the security posture of CAPT Core v0.5.0 as an installable
verification substrate. It is bounded by the evidence listed below. It does NOT
constitute a formal third-party audit, penetration test, or certification.

## Evidence collected (regenerated at candidate SHA)

| Check | Command | Result |
|---|---|---|
| Secret scan | `gitleaks detect --no-banner -v` | no leaks found (116 commits scanned, ~47 MB) |
| Runtime self-verify | `python verify_runtime.py` | 52 pass / 1 warn / 0 fail / 0 skip (53 checks) |
| Doctor injection | `pytest tests/test_doctor_sh_command_injection.py` | 5 passed |
| Security/token/injection suite | `pytest tests/ -k "injection or security or token"` | 35 passed, 44 skipped |
| No-network import | socket-deny import of core packages | PASS (zero network on import) |
| Zero Hermes import | grep installed wheel for `import hermes` | 0 matches |
| ATE provenance pin | `AntiTokenExtractionComponent.verify_pinned_commit` | present (optional external pkg, degrades) |

## Security controls present

1. **Local-first, no required network.** Core imports perform no network
   activity. PULSE is an optional gateway, disabled by default, lazy-imports its
   network library only after explicit configuration. Verified by socket-deny
   import test.

2. **No hidden harness dependency.** Zero `import hermes` in the installed
   package. Hermes is an optional integration target, not an architectural
   dependency. Verified by grep of the installed wheel.

3. **Anti-token-extraction (ATE).** `capt_solo.components.anti_token_extraction`
   provides tool-output token extraction with a pinned upstream commit
   (`verify_pinned_commit`). The external package is OPTIONAL: the component
   degrades gracefully when it is not installed (its test is `skipif` without
   the package). No secret, key, or credential is bundled.

4. **Doctor command-injection resistance.** `doctor.sh` does not interpolate
   shell variables into generated Python source. 5 injection tests pass.

5. **Release-security CI.** `.github/workflows/release-security.yml` runs
   gitleaks, `capt release validate`, and the ATE test on push. It does NOT pin
   an external `git+` dependency (the main-branch version did; this was
   synthesized during OD-4 convergence to use the in-tree component).

6. **Reproducible verification.** Verification is bound to repository + runtime
   state through VSI (`capt_solo.verification.identity`). 14 VSI tests pass.

## Known limitations (not blockers)

- ATE depends on an optional external `anti-token-extraction` package that is
  NOT bundled. When absent, ATE is a no-op. This is by design (degradable).
- `bandit`, `semgrep`, and `pip-audit` were not run locally at this SHA. They
  are wired into `release-security.yml` and run on push to the protected branch
  (owner-gated publication step). Their absence locally is a process gap, not a
  known vulnerability.
- The release validator (`capt release validate`) is a structural gate, not a
  vulnerability scanner.

## Claim alignment
- "Secure" (whitepaper title): supported by items 1–5 above.
- "Auditable": supported by append-only CTP receipts, VSI state binding, and
  evidence provenance (EvidenceRecord with provenance_chain).

## Classification of this report
This document is generated release evidence. It introduces no new public claim
beyond what the code, tests, and runtime evidence already support.
