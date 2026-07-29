# Dependency Audit

## Scope

Runtime dependencies declared in `pyproject.toml` for the `0.5.0` candidate.

## Method and result

On 2026-07-29, `pip-audit 2.10.1` was installed in a temporary isolated virtual
environment after the system Python correctly rejected an externally managed
environment install. The declared dependency set (`pyyaml>=5.4`) was audited.

Result: `No known vulnerabilities found`.

This is an advisory-database result at scan time, not a claim that future
vulnerabilities cannot be disclosed. No dependency or lockfile changed.
