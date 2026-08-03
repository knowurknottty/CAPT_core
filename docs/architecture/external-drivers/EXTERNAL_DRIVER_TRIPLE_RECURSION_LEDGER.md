# External Driver Triple-Recursion Ledger (Gate A — OpenHarness)

Three passes: Construct → Adversarial review → Reconcile. Only auditable findings
recorded.

## Pass 1 — Construct

- Selected OpenHarness 0.1.9 (candidate 1) per selection rule; installed in
  isolated py3.12 venv; pointed at local Ollama.
- Built adapter package `capt_runtime/external_drivers/openharness/` (adapter,
  translation, lifecycle, sandbox, receipts, errors, __init__).
- Adapter shells out to genuine `oh`; no OpenHarness Python import at base time.
- Wrote Gate A test suite (conformance + adversarial + removal/swap).
- Wrote 10 documentation artifacts.

## Pass 2 — Adversarial review

Challenged: framework ownership, authority leakage, hidden CAPT state access,
sandbox escape, context leakage, forged output, lifecycle mismatch, restart
ambiguity, contract drift, dependency substitution, removal failure.

Findings:
- F1: OpenHarness defaults `api_format` to `anthropic` and ignores
  `OPENHARNESS_BASE_URL` unless `api_format` is forced to `openai`. If not forced,
  the harness contacts a hosted Anthropic-compatible endpoint (401 observed).
  → Corrected by writing a sandboxed config dir with `api_format: openai` +
    localhost base_url; verified genuine local execution.
- F2: Hosted credentials in the agent env would leak to `oh` if not stripped.
  → Corrected: `sandbox.build_allowlisted_env` removes all hosted keys; verified
    only localhost Ollama contacted.
- F3: `verify_lease` does NOT enforce max-use exhaustion (`used >= maxUses`).
  → This is a FROZEN M0-B gap, not introducible by Gate A. Documented as xfail +
    security review + this ledger. NOT modified (requires owner authorization).
- F4: `resume` is not natively supported by one-shot `oh -p`.
  → Honestly declared `resumeSupported: false`; `resume()` raises; no fake resume.

## Pass 3 — Reconcile

| ID | Finding | Affected files | Correction | Evidence | Residual |
|----|---------|----------------|-----------|----------|----------|
| F1 | api_format default anthropic | adapter.py / sandbox.py | sandboxed settings.json forces openai+localhost | live oh test passes; Ollama log shows local POST | none |
| F2 | hosted key leakage | sandbox.py | strip all hosted keys in allowlist | only 127.0.0.1:11434 contacted | none |
| F3 | max-use not enforced | capability.py (frozen) | documented xfail; not modified | test_lease_max_use_exhausted_rejected xfail | owner ADR needed to fix frozen code |
| F4 | resume unsupported | lifecycle.py / adapter.py | descriptor resumeSupported=false; resume raises | test_resume_is_honestly_unsupported | none (honest) |

## Contract drift status

- No frozen contract (schema 1.0.0) field, enum, or semantic changed.
- Adapter implements the existing `ExecutionDriver` Protocol unchanged.
- `pyproject.toml` added (pytest marker config only; deselects `slow` by default).
- `external_driver_requirements.lock` added (dependency lock, gitignored intent).

## Residual uncertainty

- OpenHarness source not line-audited (third-party; run with least authority).
- Local model quality is environment-specific; not a CAPT intelligence claim.
- Max-use enforcement gap requires separate owner-authorized fix.
