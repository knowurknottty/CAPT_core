# Maintaining CAPT Core documentation

> For contributors and documentation agents. **Scope:** instructions reviewed with repository `AGENTS.md` and RRDS-1 at `0d8e46d` on 2026-10-18. This file is a maintenance process, not a declaration that every documentation check is installed in CI.

## Canonical ownership

Use a single authoritative page per topic and link to it from [the index](README.md). Update existing pages before creating duplicates.

| Reader need | Canonical source |
|---|---|
| Main entry point / product positioning | [root README](../README.md) |
| Install and first use | [Start Here](../START_HERE.md), [Installation](INSTALLATION.md) |
| Role pathways | [Onboarding](ONBOARDING.md) |
| User workflows | [User guide](USER_GUIDE.md), [TUI](TUI.md) |
| Command and programmatic interfaces | [CLI](CLI.md), [generated API](API.md) |
| Implementation/authority semantics | [Technical manual](TECHNICAL_MANUAL.md), [Architecture](ARCHITECTURE.md), [Governance](GOVERNANCE.md) |
| Source maturity and uncertainty | [Current-state snapshot](CURRENT_STATE.md), [Capability matrix](CAPABILITY_MATRIX.md) |
| Security and release claim scope | [Security](SECURITY.md), [Release evidence](RELEASE_EVIDENCE.md) |
| Historical reports | Keep their original date, SHA and scope, link rather than rewriting |

**API warning:** `docs/API.md` is generated. Inspect [`scripts/generate_api_reference.py`](../scripts/generate_api_reference.py) and [`tests/test_api_reference.py`](../tests/test_api_reference.py); don't silently hand-edit generated signatures.

## Change checklist

1. **Pin** the current repository URL, SHA, branch/worktree, `git status --short`, and any pre-existing modifications.
2. **Read** applicable [`AGENTS.md`](../AGENTS.md) plus [RRDS-1](workflows/CAPT_REVIEWER_VERIFIER_CONTRACT.md). Preserve historic evidence and authorship.
3. **Trace** every new feature statement to a concrete source path/symbol and applicable tests, rather than older prose or an issue title.
4. **Classify** the evidence: source present, tested, integrated, installed, proven live, or release proven. Do not treat the terms as synonyms.
5. **Edit canonical docs** and ensure a link from [the docs index](README.md). Provide both novice and specialist navigation when appropriate.
6. **Validate** Markdown paths/anchors and code blocks; test read-only help locally; test provider/network/side-effect examples only with specific owner authorization.
7. **Run selected tests** that cover changed contracts. A failure, omission or blocked environment must remain visible.
8. **Review three times:** coverage/navigation → adversarial factual/security review → fresh-reader execution/accessibility. Record concrete corrections.
9. **Report** exact commands, outputs, residual risks, and owner decisions. Preserve the original status of historical release receipts.
10. **Seek authorization** before committing, pushing, merging, triggering billed providers or altering CI/security/release policy.

## Low-risk verification commands

From the repository root in an appropriate development environment:

```zsh
git rev-parse HEAD
git status --short
git diff --check
capt --version
capt --help
python -m pytest -q tests/test_api_reference.py tests/test_capt_repo_audit_gate.py
```

These are **examples of checks to run**, not assertions about your environment. In particular, run `capt` only after activating the intended virtual environment; use `.venv/bin/capt` when testing an existing checkout's local venv.

### Documentation and source drift signals

- A new/renamed CLI parser argument should trigger review of `CLI.md`, `START_HERE.md`, `ONBOARDING.md`, and cheatsheets.
- Public `capt_solo.api` changes require API generation and corresponding tests.
- Runtime authority or state-transition changes require `GOVERNANCE.md`, `ARCHITECTURE.md`, and relevant user-guide updates.
- Provider/media changes require explicit separation of configuration/fixture, live acceptance and release claims.
- Native UI additions must not imply signed distribution.
- Exact-SHA receipts and dated milestones cannot silently be promoted to a later HEAD.
- Repo/source security changes require authoritatively reviewing `SECURITY.md` without inventing a disclosure policy.

## Verification boundaries

The OMEGA initial write pass conducted selected local help/tests and a tracked-file SHA-256 census. **A full deep review is not complete** merely because the census exists. RRDS-1 requires every in-scope source-bearing file receipt, independent verification, and its gate. Do not claim `DEEP_COVERAGE_GATE_PASS` without that evidence.

**Proposed, not installed:** an unprivileged Markdown-path/anchor checker and PR docs-impact checklist can help prevent drift. Review existing CI before adding a workflow, and keep privileges read-only.

[Documentation index](README.md) · [OMEGA mission record](missions/OMEGA_20261018_STATUS.md)
