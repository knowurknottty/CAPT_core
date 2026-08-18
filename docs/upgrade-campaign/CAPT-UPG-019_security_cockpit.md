# CAPT-UPG-019: Security Closure Cockpit

- **Campaign ID**: `CAPT-UPG-019`
- **Issue**: #86
- **Branch**: `upgrade/capt-upg-019-security-cockpit`
- **Disposition**: `IMPLEMENTED_PENDING_EXACT_HEAD_VERIFICATION`

## Implementation

`capt_ui/operator/security_cockpit.py` converts existing `SecurityGateResult` data into a truthful operator projection:

- PASS / FAIL / NOT_VERIFIED / NOT_APPLICABLE remain distinct;
- stale evidence is explicitly identified from gate reason/state;
- missing evidence remains NOT_VERIFIED;
- current gate blockers are preserved;
- source SHA and evidence refs remain visible per control;
- the view explicitly sets `releaseAuthorized: false` and `globalSecurityVerdict: null`;
- gate PASS is documented as a narrow result over the supplied profile/source/evidence, not a universal security claim.

`desktop/security_cockpit.py` provides a standalone Tk/Aqua cockpit and headless JSON mode. It evaluates the existing CAPT security gate rather than implementing a competing security authority.

`pyproject.toml` adds:

```text
capt-security-cockpit = desktop.security_cockpit:main
```

## Tests authored

`tests/test_security_cockpit.py` covers:

1. PASS / FAIL / missing / stale / N-A separation;
2. blocker/count preservation;
3. an inconsistent PASS decision with blocking controls is projected as BLOCKED;
4. summary text explicitly refuses a universal security verdict.

## Verification boundary

No exact-head execution is available from the connected environment. No pytest, installed-wheel, or rendered-GUI PASS is claimed.

Minimum evidence:

```bash
pytest tests/test_security_cockpit.py tests/capt_runtime/test_security_gate.py tests/capt_runtime/test_security_evidence.py
capt-security-cockpit --profile <profile.json> --evidence <evidence.json> --source-sha <sha> --headless
```

plus installed-wheel/desktop smoke verification before owner-ready integration.
