# SECURITY_TRUST_READINESS

Generated: 2026-07-30. Status vocabulary (doc 08): IMPLEMENTED_AND_EVIDENCED,
IMPLEMENTED_NOT_FULLY_EVIDENCED, PARTIAL, NOT_APPLICABLE, PLANNED,
REQUIRES_ORGANIZATIONAL_CONTROL. The Treasure Chest forbids unsupported
compliance claims — no certification is asserted here.

## 1. Engineering controls (code-level)

| Control | Status | Evidence |
|---|---|---|
| No network on core import | IMPLEMENTED_AND_EVIDENCED | socket-deny import test today, clean venv, no Hermes |
| No secrets in repo | IMPLEMENTED_AND_EVIDENCED | `git grep` for sk-/ghp_/AKIA/private-key/xoxb- across audited set = clean; `.gitleaks.toml` exists on main |
| Command-injection hardening (doctor/run_command) | IMPLEMENTED_AND_EVIDENCED | `test_doctor_sh_command_injection` etc. in today's 715 |
| Provenance on records | IMPLEMENTED_AND_EVIDENCED | `provenance` field default "hermes"/local on records |
| Idempotent security feedback | IMPLEMENTED_AND_EVIDENCED | CTP idempotency keys + tests |
| Local-first data handling | IMPLEMENTED_AND_EVIDENCED | state dir local; no cloud in core |
| Secret scanning CI | IMPLEMENTED_NOT_FULLY_EVIDENCED | `.gitleaks.toml`+`release-security.yml` on MAIN only; not yet on integration; not run against 716ecc9 |
| Deterministic security pass (bandit/semgrep/pip-audit) | PLANNED | campaign doc 04 not yet executed against current candidate |
| Codex deep scan | SUPERSEDED | doc 11: corroboration only, run late, budget explicitly |

## 2. Documentation / generated evidence

| Artifact | Status | Evidence |
|---|---|---|
| Threat model | PLANNED | docs/THREAT_MODEL.md absent |
| Security boundaries | IMPLEMENTED_AND_EVIDENCED | `SECURITY_BOUNDARIES.md` present on integration |
| Responsible disclosure | PLANNED | no SECURITY.md |
| Secure dev process | PARTIAL | ADRs + validator gate exist; no written process doc |
| SBOM | PLANNED (trivial) | runtime deps = pyyaml only; generate via `pip freeze`/syft at freeze |
| Dependency evidence | PARTIAL | pyproject pinned minimal; no lockfile or audit artifact at SHA |
| Supply-chain evidence | PLANNED | reproducible build not yet demonstrated (build ran, hash recorded, but not sealed/reproducible-claimed) |
| Privacy & data handling | PARTIAL | local-first proven; dedicated doc absent |
| NIST SSDF mapping | PLANNED | doc 08 phase 2 |
| NIST AI RMF mapping | PLANNED | doc 08 phase 2 |
| OWASP LLM/software mapping | PLANNED | doc 08 |
| ISO 27001 mapping | PLANNED (positioning) | doc 08; REQUIRES_ORGANIZATIONAL_CONTROL for any attestation |
| SOC 2 mapping | PLANNED (positioning) | doc 08; REQUIRES_ORGANIZATIONAL_CONTROL |

## 3. Separation (per mission)

- Engineering controls: above §1 — real code, real tests.
- Documentation: §2 first block — written artifacts to be produced.
- Generated evidence: SBOM, scan JSON, coverage — produced at freeze, tied to
  the frozen SHA (doc 07).
- External organizational obligations: ISO 27001 / SOC 2 attestations —
  REQUIRES_ORGANIZATIONAL_CONTROL; CAPT may publish a *support mapping* but
  never a compliance claim. This is honored: no such claim exists today.

## 4. Readiness verdict for v0.5.0 (per V0_5_SCOPE_RECONCILIATION §4)

Required for a truthful "secure, auditable" public claim:
- Run the deterministic security pass (bandit/semgrep/gitleaks/pip-audit) at
  the frozen SHA → PLANNED, must complete before freeze.
- Produce SECURITY.md (responsible disclosure) + THREAT_MODEL.md → PLANNED.
- SBOM + supply-chain statement → PLANNED, trivial.
- Standards mappings → split: SSDF/AI-RMF/OWASP mappings are reasonable v0.5.0
  support docs; ISO/SOC2 are v0.5.1 positioning (REQUIRES_ORGANIZATIONAL_CONTROL).

No certification is claimed. Status remains NOT READY until the PLANNED items
above are executed and sealed at the frozen SHA.
