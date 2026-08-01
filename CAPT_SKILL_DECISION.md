# CAPT_SKILL_DECISION.md

Binding decisions for the `capt-core-runtime` Hermes skill. Each decision cites
the evidence in `CAPT_SKILL_SOURCE_MAP.md` (SM) / `CAPT_SKILL_CONFLICT_AUDIT.md` (CA).

## D1 — Source of truth: tracked in the CAPT repository

**Decision.** The canonical skill source is tracked at
`skills/hermes/capt-core-runtime/` in the CAPT repository. `~/.hermes` is an
install target, never the source.

**Not** `capt_solo/skills/` (SM §8): that path is package-data limited to
`skills/*/SKILL.md` by `pyproject.toml` and `MANIFEST.in`, so `references/`,
`scripts/`, and `schemas/` would be silently dropped from any built wheel. A new
top-level `skills/hermes/` tree keeps the multi-file package intact and does not
disturb the existing 8 bundled skills or their packaging contract.

## D2 — Install path and mechanism

**Decision.** `~/.hermes/skills/capt/capt-core-runtime/`, installed by a tracked
script `skills/hermes/install-capt-core-runtime.sh` that performs a **copy**, not
a symlink.

- Category `capt` is a real, existing namespace directory (SM §1: one optional
  category level; `~/.hermes/skills/capt/` already holds `capt-eval-tracker`).
- Copy, not symlink: the loader `rglob`s `SKILL.md` under the skills root. A
  symlink into a git worktree would make skill content mutate under the agent
  whenever the branch is checked out elsewhere, and would break on any host
  without the checkout. Owner directive: "do not symlink unless loader behavior
  and portability support it cleanly" — they do not.
- `install.sh:56-63` is NOT reused (SM §8): it copies only `SKILL.md`, flat, with
  no provenance.

**Provenance record.** The installer writes
`~/.hermes/skills/capt/capt-core-runtime/.install-provenance.json` containing:
`source_repository`, `source_remote_url`, `source_sha`, `source_branch`,
`source_dirty`, `skill_version`, `installed_at`, `content_digest`
(sha256 over the sorted manifest of relative-path + file-sha256), `file_count`,
`installer_version`, `hermes_skills_root`.

A leading-dot filename is used deliberately: `.install-provenance.json` is not a
`SKILL.md`, so the scanner ignores it, and dot-prefixing keeps it out of casual
listings. `capt-doctor.sh` re-computes `content_digest` and reports drift.

## D3 — Boundary: loader/operator/diagnostic only

**Decision.** The skill never constructs `MemoryEngine`, `SessionRuntime`,
`LifecycleManager`, `ContextPackBuilder`, `MemoryUseGate`, `CTPRuntime`, `KHSB`,
`CapabilityRegistry`, `ProofEngine`, `ClaimGuard`, `ArtifactStore`, or a second
`CAPTRuntime`.

Enforced structurally: every script shells out to the `capt` console script
only. **No script imports `capt_solo`.** The one place a Python-level check is
needed (package resolution + version, SM §6 D-3) uses
`python -c "import capt_solo; print(capt_solo.__file__, capt_solo.__version__)"`
— an import for *identity*, which constructs nothing. A test asserts that no
script in the package contains a `CAPTRuntime(`, `MemoryEngine(`,
`MemoryUseGate(`, `KHSB(`, `CTPRuntime(`, or `.load()` construction call.

Boundary: `Hermes → capt-core-runtime skill → capt CLI → CAPTRuntime → governed path`.

## D4 — Package layout (adjusted to real loader behaviour)

```
skills/hermes/capt-core-runtime/
├── SKILL.md
├── references/            # loadable via skill_view(file_path=...)
│   ├── boot-protocol.md
│   ├── runtime-components.md
│   ├── diagnostics.md
│   ├── checkpoint-resume.md
│   ├── security-boundaries.md
│   ├── milestone-language.md
│   └── compatibility.md
├── scripts/               # loadable via skill_view; executable
│   ├── capt-doctor.sh
│   ├── capt-environment-report.sh
│   ├── capt-fresh-boot.sh
│   ├── capt-checkpoint.sh
│   └── capt-resume-check.sh
└── schemas/
    └── boot-report.schema.json
```

Deviations from the requested tree, with cause:

- **`references/` merged from 10 → 7 files.** `mission-session-memory.md`,
  `contextpack-memory-gate.md`, and `ctp-khsb-claimguard.md` are folded into
  `runtime-components.md` and `boot-protocol.md`. Reason: the loader only
  surfaces `references/` on explicit `skill_view(file_path=...)`; ten files whose
  content is three paragraphs each cost routing accuracy, not depth.
- **`tests/` NOT inside the skill package.** `tests/` is not in
  `SKILL_SUPPORT_DIRS` (SM §1) and is not reachable via `skill_view`. Tests live
  at the repository's canonical location `tests/test_hermes_capt_core_runtime_skill.py`,
  matching the existing convention (`tests/test_agent_boot.py`, etc.).
- **`schemas/` reduced to `boot-report.schema.json`.** The memory-trace,
  contextpack-manifest, and recovery-receipt shapes are *emitted by CAPT*
  (`AgentMemoryBootTrace.to_dict`, `decision.pack`, `resume_report`), not by this
  skill. Publishing a second schema for a shape the runtime already owns is the
  parallel-implementation failure mode D3 forbids. The boot report is the one
  artifact the skill itself composes, so it gets a schema.

## D5 — Trigger policy

Description leads with the CAPT Core / capt-solo product name to defeat the
bioCAPT ambiguity (CA §1) and stays within the 60-char new-skill cap
(SM §1, `SKILL_PROMPT_DESC_LIMIT = 60`):

```
description: Boot/resume CAPT Core (capt-solo) governed sessions.
```

(57 chars.) The full trigger vocabulary — "use/load/boot CAPT", "CAPT Core",
"CAPTRuntime", "CAPT mission/session", "MemoryUseGate", "ContextPack",
"ClaimGuard", "CTP", "KHSB", "resume through CAPT", "checkpoint through CAPT" —
lives in the SKILL.md body under an explicit "When this skill applies" section,
which is what the agent reads after routing.

**Negative trigger, mandatory.** The skill does not activate for generic coding
work. It requires workspace evidence: `capt` resolvable in the active
environment **and** `<workspace>/.capt/checkpoints/` present, or an explicit user
request for CAPT governance. Absent both → the skill reports
`NOT_A_CAPT_WORKSPACE` and returns control. This is stated in the first 15 lines
of SKILL.md.

## D6 — Legacy disposition (from CA §3)

Zero deletions, zero edits to existing skills. `capt-solo-v04-engineering`
retained as the *engineering* counterpart; `capt-core-runtime` is the *operating*
skill. Bundled `capt-bootstrap` / `capt-recovery` retained as legacy
compatibility and recorded as superseded-for-boot in
`references/compatibility.md`.

## D7 — Honesty contract

The skill's default self-classification inside a Hermes session is
**BOOTSTRAP_DEGRADED**, not GOVERNED, because (CA §5):

- Hermes tool hooks are observational only (CA D-5) → tool authorization is not
  runtime-enforced;
- nothing in Hermes proves the model's actual context equals the CAPT
  ContextPack.

`GOVERNED` is reserved for what `capt agent status/start` itself returns for a
CAPT-executed turn. The skill must never relabel a Hermes turn as GOVERNED
because a CAPT subprocess printed GOVERNED. Both facts are reported side by side:
`capt_execution_mode` and `hermes_session_mode`.

## D8 — Acceptance mission

Acceptance uses an **isolated test mission** in an isolated `CAPT_SOLO_HOME` and
an isolated temp workspace — never Project SEAL, never IronSight, never
`mission-governed-model-execution` (digest-broken, CA D-2), never
`mission-outer-agent-memory-continuity` (live owner mission).

Isolation contract, from `capt-solo-engineering-workflow`:
`export CAPT_SOLO_HOME="$(mktemp -d)/home"` before any command that reaches
`CAPTRuntime.load()`. Owner `~/.capt-solo` must be provably untouched afterward.
