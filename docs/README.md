# CAPT Core Documentation

This directory separates **current operator guidance**, **current architecture/reference material**, **active integration work**, and **historical evidence/planning**.

If two documents appear to disagree, use this authority order:

1. source and contracts at the exact commit being discussed;
2. exact-head tests/evidence for that commit;
3. [`CURRENT_STATE.md`](CURRENT_STATE.md) and the public capability matrices;
4. current operator guides;
5. historical release evidence, audits, ADRs, and planning documents.

A package version, merged capability, open-PR implementation, and release-proven capability are deliberately different states.

## Start here

- [Start Here](../START_HERE.md) — install and first success.
- [Current State](CURRENT_STATE.md) — what is released, merged, integrating, and unproven.
- [Mental Model](MENTAL_MODEL.md) — one-screen architecture.
- [User Guide](USER_GUIDE.md) — normal workflows.
- [TUI](TUI.md) — merged operator console and active cockpit upgrade.
- [Providers](PROVIDERS.md) — provider/model status and execution boundaries.
- [Capability Matrix](CAPABILITY_MATRIX.md) — capability-by-capability truth table.
- [Functionality Matrix](FUNCTIONALITY_MATRIX.md) — operator/runtime release view.
- [Security](SECURITY.md) — current threat model and open hardening blockers.

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

Subsystem references such as ClaimGuard, Foundry, Knowledge Bubbles, CTP/KHSB-related material, migrations, and proof documentation remain valid technical references unless a newer source contract supersedes them.

## Historical records

Release evidence, ADRs, launch audits, reconciliation reports, and old release-candidate documents are historical records. They should not be rewritten to make an old proof look current.

The former v0.6 planning documents are retained as historical planning baselines:

- [`V0_6_PRODUCTIZATION_SOURCE_OF_TRUTH.md`](V0_6_PRODUCTIZATION_SOURCE_OF_TRUTH.md)
- [`V0_6_UI_UX_PRODUCTIZATION.md`](V0_6_UI_UX_PRODUCTIZATION.md)

Their original requirements drove substantial merged work, but their old “canonical current plan” language is superseded by the present repository state and active integration stack.

## Current integration stack

At this documentation update, the active cumulative stack is:

- PR #44 — Discovery Governor / bounded local scanner;
- PR #46 — governed Hermes/Ouroboros lifecycle hardening;
- PR #47 — prompt assembly, cognitive provenance, TUI cockpit upgrade, bounded ProviderDriver integration;
- PR #48 — bounded Cohort coordination contracts;
- PR #49 — fail-closed security infrastructure gate.

Open PR code is **not** labeled shipped simply because it exists.