> SUPERSEDED — historical archaeology artifact. Authoritative live state is CURRENT_STATE.md / RELEASE_STATE.md. Branch names and SHAs here are from earlier phases and do not describe the current candidate.

# CAPT Core v0.5 P0 Baseline

- **Status:** Frozen pre-remediation evidence; not release approval
- **Captured:** 2026-07-29
- **Branch:** `codex/capt-v0.5-p0-release-hardening`
- **Reviewed SHA:** `51eda9a99cb3df84f58e37ceb2328713604e38e9`
- **Declared version:** `0.5.0`
- **Artifact scope:** Fresh wheel and sdist built from the reviewed SHA

This document records the repository and distribution state before P0 release
hardening. It is historical evidence for the defects below and must not be used
as final-candidate verification.

## Worktree State

Command:

```text
git status --porcelain=v2 --branch
```

Result:

```text
# branch.oid 51eda9a99cb3df84f58e37ceb2328713604e38e9
# branch.head codex/capt-v0.5-p0-release-hardening
? .capt_state/
```

`.capt_state/` is pre-existing, untracked, user-owned state. It is excluded from
this mission and was not read, modified, staged, or packaged.

The only existing tag was:

```text
v0.4.0
```

## Version Locations

Command:

```text
rg -n "0\.5\.0|CAPT_SOLO_VERSION|__version__|version\s*=|\"version\"" \
  pyproject.toml capt_solo/__init__.py capt_solo/plugin/plugin.json \
  capt_solo/foundry/bubble.py README.md CHANGELOG.md
```

Current declarations:

| Location | Value | Role |
|---|---:|---|
| `pyproject.toml` | `0.5.0` | distribution metadata |
| `capt_solo/__init__.py` | `0.5.0` | runtime version |
| `capt_solo/plugin/plugin.json` | `0.5.0` | Hermes plugin manifest |
| `capt_solo/foundry/bubble.py` | `0.5.0` | bubble-origin version |
| `README.md` | `v0.5.0` | public documentation |
| `CHANGELOG.md` | `0.5.0` unreleased | release history |

The package-level version declarations agree. Present-tense state documents do
not: `CURRENT_STATE.md` and `RELEASE_STATE.md` still claim `0.4.1`.

## Source Package Inventory

Deterministic method:

```text
find capt_solo -type d containing __init__.py, sort by dotted package name
```

Result: 18 importable packages and no Python namespace-package directories.

```text
capt_solo
capt_solo.contextpack
capt_solo.continuity
capt_solo.core
capt_solo.ctp
capt_solo.engines
capt_solo.evidence
capt_solo.execution
capt_solo.foundry
capt_solo.khsb
capt_solo.knowledge
capt_solo.learning
capt_solo.lifecycle
capt_solo.memory
capt_solo.ontology
capt_solo.plugin
capt_solo.research
capt_solo.verification
```

All 18 imported successfully from the source checkout. `capt_solo.skills` is a
runtime data tree, not an importable Python package.

## Package Discovery Configuration

`pyproject.toml` uses a manually maintained 15-package list. It omits:

```text
capt_solo.evidence
capt_solo.ontology
capt_solo.verification
```

The build also warned that `capt_solo.skills` is ambiguous under the explicit
package configuration. Package data happened to enter the artifacts through the
generated source manifest rather than an explicit durable contract.

## Fresh Baseline Build

Command:

```text
python3 -m build --outdir \
  /var/folders/1c/zqvsbr7575xfd767m1w2686m0000gn/T/\
capt-v0.5-p0-baseline.XXXXXX.d7Vq9rhUhp/dist
```

Result:

```text
Successfully built capt_solo-0.5.0.tar.gz and
capt_solo-0.5.0-py3-none-any.whl
```

Baseline hashes:

```text
20369ad5a9fe4cfba90f6646834ed1d9780d4807c6d5d89a4045b7406f17c0be  capt_solo-0.5.0-py3-none-any.whl
3e828add8df068c66de8abd6f142ebcd7eb36be17771ce8f3a241da15e962403  capt_solo-0.5.0.tar.gz
```

These are pre-remediation hashes and are not release artifacts.

## Built Wheel Inventory

The wheel contained 90 files and these 15 Python packages:

```text
capt_solo
capt_solo.contextpack
capt_solo.continuity
capt_solo.core
capt_solo.ctp
capt_solo.engines
capt_solo.execution
capt_solo.foundry
capt_solo.khsb
capt_solo.knowledge
capt_solo.learning
capt_solo.lifecycle
capt_solo.memory
capt_solo.plugin
capt_solo.research
```

It contained `plugin.json` and eight bundled `SKILL.md` files. It did not contain
Evidence, Verification, or Ontology. It also installed no `capt` CLI executable.

## Built Sdist Inventory

The sdist contained 177 files and the same 15 Python packages as the wheel. It
also omitted Evidence, Verification, and Ontology.

The sdist unintentionally included 55 repository test files. This is not private
user data, but it is development-only material and is not part of the v0.5
runtime distribution contract.

Neither artifact contained `.capt_state`, `.env`, credentials, or local
checkpoint paths in this inspection.

## Advertised Public Capabilities

The current documentation, changelog, canonical architecture, plugin manifest,
and architecture review advertise or depend upon these package-level
capabilities:

| Capability | Current source package | Artifact expectation |
|---|---|---|
| Evidence | `capt_solo.evidence` | public, provisional |
| Verification/VSI | `capt_solo.verification` | public, provisional |
| ContextPack v1 | `capt_solo.contextpack` | public, stable v1 schema |
| Transactions | `capt_solo.ctp` | public, stable compatibility surface |
| KHSB | `capt_solo.khsb` | public, stable compatibility surface |
| Memory | `capt_solo.memory` | public, stable compatibility surface |
| Foundry | `capt_solo.foundry` | public, provisional |
| Workspace | `capt_solo.workspace` | public CLI/module surface |
| Governance | `capt_solo.foundry.governance` | public, provisional |
| Plugin | `capt_solo.plugin` plus data | public, stable compatibility surface |
| Ontology | `capt_solo.ontology` | public vocabulary implementation, provisional |
| Full runtime facade | `capt_solo.api` | public compatibility facade |

The source checkout makes these importable. The baseline artifacts do not.

## Installed-Wheel Behavior

The baseline wheel was installed into a fresh Python 3.14 virtual environment
from outside the repository checkout.

Install result:

```text
Successfully installed capt-solo-0.5.0 pyyaml-6.0.3
```

Import results:

```text
PASS capt_solo
PASS capt_solo.contextpack
FAIL capt_solo.continuity: No module named 'capt_solo.evidence'
PASS capt_solo.core
PASS capt_solo.ctp
PASS capt_solo.engines
FAIL capt_solo.evidence: No module named 'capt_solo.evidence'
PASS capt_solo.execution
PASS capt_solo.foundry
PASS capt_solo.khsb
FAIL capt_solo.knowledge: No module named 'capt_solo.ontology'
FAIL capt_solo.learning: No module named 'capt_solo.ontology'
PASS capt_solo.lifecycle
PASS capt_solo.memory
FAIL capt_solo.ontology: No module named 'capt_solo.ontology'
PASS capt_solo.plugin
PASS capt_solo.research
FAIL capt_solo.verification: No module named 'capt_solo.verification'
```

The three direct omissions therefore break six advertised package imports.

## Existing Security-Scan State

`docs/RELEASE_SECURITY_REPORT.md` explicitly says the repository-wide scan is
active, unsealed, and not release clearance. No canonical v0.5 findings,
coverage, or manifest JSON exists under `docs/security/`.

The earlier dependency audit records `pip-audit 2.10.1` and no known
vulnerabilities for the declared `pyyaml>=5.4` requirement on 2026-07-29. That
historical result must be rerun for the final candidate.

## Stale Present-Tense Authority

- `CURRENT_STATE.md` describes branch `integration/full-public-architecture`,
  SHA `27ce5fc`, version `0.4.1`, and 550 tests.
- `CHECKPOINT.md` resumes Physics implementation from `27ce5fc`.
- `TASK_QUEUE.md` marks already completed workspace, licensing, and version work
  as ready.
- `RELEASE_STATE.md` claims version `0.4.1`, 502 tests, and no code-level blocker.
- `docs/API.md` and `docs/ARCHITECTURE.md` still identify v0.1 and describe
  `capt_solo.api` as the sole sanctioned public surface.
- `README.md` claims zero network while separately documenting optional PULSE
  networking, and carries stale test-count claims.
- canonical ownership and architecture prose contains historical “missing” and
  “wheel only” implementation claims contradicted by the current tree.

The current workspace validator accepts checkpoint ancestry and document
structure; it does not detect this semantic drift.

## Baseline Release Blockers

1. Wheel and sdist omit three advertised packages.
2. Installed-wheel imports fail for six package profiles.
3. No installed `capt` CLI exists.
4. Sdist contents are not explicitly controlled.
5. Public API ownership and stability tiers are undeclared.
6. Current authority documents contradict the current candidate.
7. No semantic freshness release gate exists.
8. No installed-artifact profile or tutorial conformance gate exists.
9. The security scan is unsealed.
10. No final exact-SHA artifact and evidence bundle exists.

**Baseline decision:** `NOT READY — BLOCKERS REMAIN`.
