# CAPT Core Documentation

This directory separates **current operator guidance**, **current architecture/reference material**, **active work**, and **historical evidence/planning**.

If two documents appear to disagree, use this authority order:

1. source and contracts at the exact commit being discussed;
2. exact-head tests/evidence for that commit;
3. [`CURRENT_STATE.md`](CURRENT_STATE.md), [`PR_TOPOLOGY.md`](PR_TOPOLOGY.md), and the public capability matrices;
4. current operator guides;
5. historical release evidence, audits, ADRs, branch reports, and planning documents.

A package version, merged capability, branch-local implementation, exact-head verification, and release-proven artifact are deliberately different states.

## Start here

- [Start Here](../START_HERE.md) — install and first success.
- [Current State](CURRENT_STATE.md) — concise current source/evidence boundary.
- [PR Topology](PR_TOPOLOGY.md) — current branch/PR routing map.
- [Mental Model](MENTAL_MODEL.md) — one-screen architecture.
- [User Guide](USER_GUIDE.md) — normal workflows.
- [TUI](TUI.md) — operator console.
- [Providers](PROVIDERS.md) — provider/model status and execution boundaries.
- [Authored Skills](AUTHORED_SKILLS.md) — pinned-external and managed-local skill context.
- [Capability Matrix](CAPABILITY_MATRIX.md) — capability-by-capability truth table.
- [Functionality Matrix](FUNCTIONALITY_MATRIX.md) — operator/runtime release view.
- [Security](SECURITY.md) — threat model and SHA-bound security evidence.

## Current technical references

- [Architecture](ARCHITECTURE.md)
- [Design](DESIGN.md)
- [CLI](CLI.md)
- [API](API.md) — **source-generated**; do not hand-edit without updating the generator.
- [Runtime / Integration Guide](PLUGIN_GUIDE.md)
- [Desktop](DESKTOP.md)
- [Installation](INSTALLATION.md)
- [Troubleshooting](TROUBLESHOOTING.md)
- [Release Evidence](RELEASE_EVIDENCE.md)
- [Roadmap](ROADMAP.md)
- [Whitepaper](WHITEPAPER.md)

Subsystem references such as ClaimGuard, Foundry, Knowledge Bubbles, CTP/KHSB, replay, Cohorts, ToolBroker/ToolExecution, migrations, and proof documentation remain technical references unless a newer source contract supersedes them.

## Current merged milestones

The public documentation should assume the following are already merged into Core `main`, while keeping their proof boundaries separate:

- PR #117 — provider/native/UPG-001→019/MCP convergence;
- PR #126 — governed ToolBroker and initial local/SSH/Docker terminal backends;
- PR #128 — owner-approved public-release design + implementation plans preserved on current main as documentation authority only;
- PR #129 — managed-local Agent Skills import/verify, contextual selection, approval binding, anti-drift, and native visibility.

Do not regress current docs to the old PR #44/#46/#47/#48/#49 “active integration stack.” Those branches are historical implementation lineage, not the present Core topology.

## Current open Core work

As of 2026-08-27, the open Core PR lane is CAPT-UPG-020→024:

- #89 reciprocal-review benchmark;
- #91 sparse symbol-index probe;
- #93 Tree-sitter structural-hash probe;
- #95 FastCDC/content-defined chunk probe;
- #97 cognitive-debt cockpit.

The Inversion Labs/Forge line is a separate edition/history lineage rather than an open Core-main stack. The approved public-release design/plans are now present on `main` through #128, but their product features remain implementation work until separately proven.

## Historical records

Release evidence, ADRs, launch audits, reconciliation reports, superseded PR plans, and old release-candidate documents are historical records. They should not be rewritten to make an old proof look current.

The former v0.6 planning documents remain historical baselines:

- [`V0_6_PRODUCTIZATION_SOURCE_OF_TRUTH.md`](V0_6_PRODUCTIZATION_SOURCE_OF_TRUTH.md)
- [`V0_6_UI_UX_PRODUCTIZATION.md`](V0_6_UI_UX_PRODUCTIZATION.md)

Their old “canonical current plan” language is superseded by current source and the approved public-release design/plans preserved via PR #128.

## Evidence rule

A green test suite, a merged commit, a successful tool/provider run, a Security Closure Cockpit receipt, an installed artifact, and a signed/notarized public release are different evidence classes. Cite the exact source identity and the smallest claim it supports.
