# VERIFICATION REPORT — RRDS-1

**Target:** `c956c45e33119cd31ce7e61c55334e803f20bf3f`
**Overall assessment: PARTIAL. Independent deep-review sign-off is withheld.**

All 681 source files were independently enumerated and hashed. **I did not semantically inspect all 681 files.** Structural verification and the critical-path checks below do not establish semantic completeness.

## 1. Target and independence

**PASS — correct target.** `git rev-parse HEAD` returned the exact requested SHA before and after verification. The checkout is detached; Git status was clean.

Analysis used this worktree’s source, local Git objects, and the four supplied evidence artifacts. No network service, provider, runtime ledger, or approval service was called. No repository files or branches were changed.

Local Git history contains `40e9a964be9b3bf5480ffd04ebc62364988b978b`, the later PR #223 merge. Its fixes were **not** substituted for the target source.

PR #224 and PR #225 remain drafts according to the supplied task context; their remote status was not independently queried. The local PR #225-associated branch contains the `.git` metadata exclusion, which is **absent from this target**.

## 2. Independent census, hashes, and line receipts

Enumeration used:

```text
git ls-tree -rz --full-tree c956c45e33119cd31ce7e61c55334e803f20bf3f
git cat-file --batch
```

An independent Python pass compared Git blob bytes, verifier-worktree bytes, census hashes, dossier hashes, and inspection hashes. Source suffixes were explicitly enumerated rather than taking the dossier’s count.

| Check | Independent result |
|---|---|
| Git-tracked paths | **1,032** |
| Source files | **681** |
| Source-bearing directories | **47** |
| Source bytes | **6,224,814** |
| Source lines, using `splitlines()` | **144,212** |
| Tracked worktree/blob byte mismatches | **0** |
| Census/tracked-file digest mismatches | **0** |
| Source dossier/inspection digest mismatches | **0** |
| Missing source paths or duplicate receipts | **0** |
| Source classification differences | **0** |
| Recursive directory differences | **0** |
| Symlinks | **0** |
| Declared exclusions or census errors | **0** |
| Declared critical paths | **411** |

The census has **1,033 records**, because it additionally hashes the untracked, checkout-specific root `.git` pointer. This is not a missing or additional source file.

### Line verification

I checked both sets of per-file line receipts and all **5,617 listed declaration references** against source:

- **647 files:** cited single-line symbols occur at the cited lines.
- **33 files:** structural ranges are in bounds. These are range annotations, not semantic-review evidence.
- **1 file:** `tests/__init__.py` is empty, but its receipt says `L1: empty source file`. There is no line 1. The empty-file description is accurate; the line locator is invalid.
- **5,617 declarations:** no cited declaration-symbol mismatch found.

Thus, file accounting passes, but literal line-reference validity is not completely clean.

### Artifact fingerprints

| Artifact | SHA-256 |
|---|---|
| `automated-full-source-inspection.json` | `197b3c248ae2864839fc22a030f491fb6fe3a06bb42c530b594b03513f8920d6` |
| `reviewer-census.json` | `b802cd56aa6b79d247b70adbe610676d204e72cb14f58c7c481b070ae1965eed` |
| `full-structural-inspection.json` | `0daddb6bbcf51ae3916eb8cf04c7631499346ac588a7d236e7679abc98a12c04` |
| `full-structural-verdict.json` | `4bf357dcaee8e62ec247bab24093d85cb494164cff5590fd902fbf2af1528ff5` |

## 3. Node evidence and mechanical gate

All 681 inspection rows reference:

```text
capt-node:omega-rrds-c956-full-scan-20261018-02
```

The dossier explicitly identifies its reviewer as `deterministic-ast-and-source-line-analyzer` and labels its inspection `automated_structural_not_human_line_review`.

The operation’s authenticity is stipulated by the task. Independently, I verified that the resulting artifact accurately describes the source bytes and listed symbols. **The supplied files do not independently authenticate the underlying journal event:** no journal export or cryptographic operation-to-artifact binding accompanied the JSON in its directory.

The reference is specific enough to name an operation, but does not itself establish human comprehension, per-file semantic conclusions, or independent approval.

Executed:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/capt_repo_audit_gate.py verify \
  --census /tmp/omega-rrds-c956c45e.ronkSQ/reviewer-census.json \
  --inspection /tmp/omega-rrds-c956c45e.ronkSQ/full-structural-inspection.json
```

Result: **`DEEP_COVERAGE_GATE_PASS`**, 681/681 files and 47/47 source directories.

Important qualification: this CLI follows the census’s embedded **reviewer** root. Independent comparisons against the **verifier** worktree were performed separately.

## 4. Falsification results

These probes invoked the real target `verify()` function with in-memory copies of the supplied JSON. No source, evidence file, or function implementation was changed.

| Probe | Actual result | Assessment |
|---|---|---|
| Original artifacts | `DEEP_COVERAGE_GATE_PASS` | Expected |
| Retain only six root-level source receipts | `PARTIAL_OR_UNVERIFIED` | **PASS:** shallow scan rejected |
| Remove `benchmarks/chunk_stability.py`, retaining its directory’s other receipts | `PARTIAL_OR_UNVERIFIED`, 680/681 | **PASS:** directory coverage cannot substitute for file coverage |
| Replace that file’s frozen digest with zeros | Changed-bytes and receipt-hash errors | **PASS:** frozen-digest falsification detected |
| Replace **every** line receipt with `L999999: fabricated_symbol`, and every journal reference with `not-a-journal` | **`DEEP_COVERAGE_GATE_PASS`** | **FAIL:** fabricated receipts accepted |
| Set every census `source` and `risk` flag false, clear source directories, supply zero inspection rows | **`DEEP_COVERAGE_GATE_PASS`, 0/0** | **FAIL:** source coverage can be erased through census metadata |
| Change only the in-memory census root to this verifier worktree | `PARTIAL_OR_UNVERIFIED`: `changed bytes: .git` | **FAIL:** checkout metadata prevents portable verification |

The altered-digest probe is **not** claimed as execution of the existing source-mutation fixture.

### Existing tests

Attempted:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
python3 -m pytest -p no:cacheprovider -q tests/test_capt_repo_audit_gate.py
```

**NOT RUN:** pytest failed during capture initialization:

```text
FileNotFoundError: [Errno 2] No usable temporary directory found
```

A subsequent capture-disabled attempt on `tests/capt_runtime/test_dead_context_paths.py` produced five setup errors for the same temporary-directory blocker. `tests/conftest.py:15–18` requires a writable `tmp_path` through an autouse fixture.

Therefore, existing shallow-scan, altered-source, and directory-omission fixtures, integration tests, and Swift tests receive **no execution credit** here. Their source was inspected where noted. Git also emitted denied temporary-cache warnings, although the reported read operations returned their requested data.

## 5. Independently selected semantic checks

These are bounded source checks, **not whole-file semantic certifications**. “Observed” denotes code inspection; tests mentioned here were inspected, not passed in this session.

| # | Source receipt | Semantic observation |
|---|---|---|
| 1 | `capt_runtime/provider_model_preflight.py:33–76` | Exact origin, credential requirement, bounded response, and image-ID/modality checks exist. Text responses require only a string `id`, without comparing it to the requested model. **Confirmed gap.** |
| 2 | `capt_runtime/drivers/provider.py:943–975` | Official OpenRouter preflight precedes inference; prompt-digest checking occurs before inference headers are used. Preflight success is not inference or paid-provider acceptance. |
| 3 | `capt_runtime/provider_endpoint.py:15–35` | Credentialless local classification checks loopback, with a separate unconditional Ollama credential exemption. Credential policy must not be mistaken for network authorization. |
| 4 | `capt_runtime/model_authority.py:101–152` | Normalization binds filesystem roots and explicit mutation/shell permissions. Provider network policy separately rejects remote endpoints under `local_only`. |
| 5 | `capt_runtime/model_approval_binding.py:98–135` | Approval digest incorporates run identity, requested context budget, dispatch-prompt digest, authority profile, and tool-schema digest. This is substantive binding, not a prompt-only approval. |
| 6 | `capt_runtime/prepared_execution.py:10–24` | Claimed immutable mappings inherit `dict.__ior__`. A pure in-memory probe changed a nested frozen authority value. **Confirmed immutability defect.** |
| 7 | `desktop/m1_command_service.py:1085–1132` | Preparation precedes durable admission; registered prompt expectation precedes runner execution. Replay returns without redispatch. The earlier return at 1064–1072 checks command ID before the later fingerprint-check block. |
| 8 | `capt_runtime/services.py:2187–2290` | Admission checks authority, approval identity, scope, state, expiration, and one-use status under an authority section; approval consumption and DriverRun creation share a commit. Full concurrency behavior remains unexecuted. |
| 9 | `capt_runtime/approval_dispatch.py:29–36` | Registered prompt mismatch fails closed, but an absent registration succeeds. This helper cannot establish approval for all alternate driver call sites. |
| 10 | `desktop/capt_runtime_service.py:1533–1547,1674–1727` | Preparation computes effective model context and reads authoritative approval state. Execution consumes prepared fields, revalidates authority, and resolves credentials afterward. Provider configuration is reloaded at execution, leaving configuration-drift analysis unfinished. |
| 11 | `capt_runtime/tool_broker.py:443–499,561–600,667–685` | Fingerprint and replay identity checks precede dispatch; consequential uses reserve capability; world receipts undergo structural and target verification. Post-dispatch exceptions become indeterminate. |
| 12 | `capt_runtime/world_receipt.py:54–101,105–127` | EffectIntent binds target, payload, grant/lease, expiry, and idempotency. Receipt fields must match the intent. Actual target proof depends on the broker’s adapter verification, not this comparison alone. |
| 13 | `capt_runtime/model_tool_bridge.py:161–186,274–300` | Unknown or unauthorized operations are rejected before broker execution. Requests bind run/call identity, grant, lease, scope, and fingerprint. |
| 14 | `capt_runtime/model_tool_authority.py:50–125,153–169` | Normalized authority produces run-specific grants/leases with bounded uses; revocation requires governance-kernel metadata. Durable authority still depends on service enforcement. |
| 15 | `capt_runtime/tools/adapters/terminal.py:95–139`; `capt_runtime/tools/backends/local.py:117–140,254–264` | Explicit argv, bounded execution, scoped working directory, restricted inherited environment, and `shell=False` exist. **Working-directory validation is not OS-level filesystem confinement.** |
| 16 | `capt_runtime/identity.py:70–105` | Chain verification checks linkage and selected revocations, but not expiration or scope narrowing. Scope comparison accepts arbitrary string prefixes; `mission.re` is accepted under `mission.read`. Search found delegation-validator callers in tests, not a demonstrated live authorization path. |
| 17 | `capt_runtime/memory/store.py:265–310` | `project_scope` and `trust_threshold` are accepted but unused in query filtering. Consent/sensitivity filtering does not implement project identity isolation. **Confirmed API-enforcement gap.** |
| 18 | `capt_runtime/memory/engine.py:248–278,318–379` | Retrieval omits project scope; dispatch accepts caller-provided consent/scope booleans. Missing packs and supplied digest mismatches are rejected. These checks do not prove cross-project isolation. |
| 19 | `capt_runtime/memory/contextpack.py:89–100,132–134` | Zero token budget disables budget filtering; `contextUsageAfter` adds a sum over an empty list. Accounting and zero-budget semantics require targeted follow-up before completeness claims. |
| 20 | `capt_runtime/driver_host.py:159–172`; `capt_runtime/composition.py:158–179` | Memory enforcement is conditional on an attached engine; the provider-host factory constructs a host without one. A universal “mandatory memory gate on every provider dispatch” claim is unsupported. |
| 21 | `capt_runtime/context_pipeline.py:19–33` | Explicitly `SHIPPED = False`. The architecture must not be credited as live integration. The corresponding dead-path test source confirms this distinction. |
| 22 | `capt_runtime/aggregates/bot.py:31–46`; `capt_runtime/governed_service.py:187–212` | Bot registration validates authority, requires an existing mission for delegates, and commits identity/policy state. Registration itself does not issue execution capability. |
| 23 | `capt_runtime/bot_locality.py:16–46` | Locality compilation restricts private-data placement, but is policy construction. Search found `runtime_for_data` usage in tests; this does not demonstrate universal dispatch enforcement. |
| 24 | `capt_ui/surfaces/desktop_swift/Sources/CAPTCoreDesktop/CAPTBotRegistration.swift:26–75` | Native registration rejects unsupported delegate creation, sends an idempotent runtime command, and requires matching Bot identity plus `identityOnly`. |
| 25 | `capt_ui/surfaces/desktop_swift/Sources/CAPTCoreDesktop/CAPTRuntimeClient.swift:60–81,105–128` | Native client authenticates, requires operator/session identity, and constructs command envelopes. It does not automatically replay a command after send/read failure. |
| 26 | `scripts/capt_repo_audit_gate.py:98–151`; `.github/workflows/rrds-review-depth.yml:19–27` | Gate trusts frozen classification fields and weak receipt syntax. CI invokes tests and the index checker, but neither proves semantic review or independent authorization. |

Alternate-path inspection included `capt_runtime/vessel_dispatcher.py:356–365`, which constructs its own ProviderDriver/DriverHost, and `composition.py:158–179`.

Relevant test bodies inspected include:

- `tests/capt_runtime/test_model_tool_bridge.py:139–171,207–218`: broker evidence, unauthorized operations, scope escape.
- `tests/capt_runtime/test_world_receipt.py:162–193`: tampered target receipt remains indeterminate.
- `tests/capt_runtime/test_prompt_approval_security.py:293–341`: admission identity binding.
- `tests/capt_runtime/test_identity_authority.py:63–120`: delegation/link tests, without prefix-boundary or chain-expiration coverage in those cases.

## 6. Discrepancies, severity, and implications

| Severity | Finding | Implication |
|---|---|---|
| **HIGH** | Gate derives source/risk coverage from unvalidated frozen flags: `scripts/capt_repo_audit_gate.py:136–151`. | A full source tree can receive a zero-receipt PASS. Reproduced. |
| **HIGH** | Gate checks line syntax and journal-reference truthiness only: `:132–135`. | Invented symbols, impossible line numbers, and nonexistent journals receive PASS. Reproduced. |
| **HIGH — conditional exposure** | Memory query ignores project and trust constraints: `memory/store.py:265–310`. | Those arguments provide no isolation/filtering. Actual cross-project disclosure was not exercised or established. |
| **MEDIUM** | Prepared mappings remain mutable through inherited `__ior__`: `prepared_execution.py:10–24`. | The claimed immutable admission-to-dispatch boundary is false. Mutation was reproduced; an external exploit was not demonstrated. |
| **MEDIUM** | Text preflight does not require returned model ID equality: `provider_model_preflight.py:73–76`. | Wrong-model metadata can be accepted as requested-model availability. Later PR #223 code does not repair this pinned snapshot. |
| **MEDIUM** | Root `.git` pointer is treated as project content. | Equivalent detached worktrees fail cross-root verification. PR #225’s local fix is absent here. |
| **MEDIUM — latent helper defect** | Delegation prefix matching lacks component boundaries; chain verification omits expiration/scope checks. | These helpers are insufficient as complete authorization checks. Live exploit reachability was not established. |
| **MEDIUM — certification gap** | CI has no independent-verifier approval check; its empty-index claim guard matches only literal `RRDS-1: PASS`. | Green CI cannot establish independent sign-off; differently worded completion claims are not caught by that guard. |
| **LOW** | Empty source file receives an impossible `L1` locator. | One receipt requires an explicit empty-file representation. |

The terminal confinement and conditional memory-gate observations are additional unresolved boundary limitations, not claims of demonstrated exploitation.

`docs/review-evidence/rrds-index.json` contains **zero reviews**. Executing:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/capt_repo_audit_gate.py ci \
  --index docs/review-evidence/rrds-index.json
```

printed:

```text
RRDS-1 evidence records checked: 0
```

**There are no indexed release-certifying reviews at this target.** Branch-protection enforcement was not checked offline.

The MIT license retains `Copyright (c) 2026 knowurknot`; the inspected provenance instructions remain present.

## 7. Three separate verdicts

| Verdict | Status | Scope |
|---|---|---|
| **Mechanical RRDS coverage** | **PASS — path/digest accounting only** | Independently confirmed 681/681 source files and 47/47 directories; original CLI PASS reproduced. Receipt authenticity/comprehension is not established, and one empty-file locator is invalid. |
| **Semantic deep review** | **PARTIAL** | Bounded semantic checks above; **not all 681 files semantically inspected**. Confirmed defects and unfinished cross-boundary analysis remain. |
| **Independent verifier authorization** | **FAIL — sign-off withheld** | This report does not authorize a completed-deep-review claim, release certification, merge, or cherry-pick based on the dossier. |

## 8. Smallest next corrective actions

1. **Keep this dossier classified as automated structural coverage.** Preserve its historical SHA and artifacts.
2. **Harden census validation:** derive source/risk classifications and source directories from the fresh tree; reject forged flags and duplicate census paths.
3. **Harden receipts:** validate line bounds and symbols, represent empty files explicitly, and bind journal evidence to the pinned artifact digest. Keep semantic assessment separate.
4. **Apply and test the worktree-metadata correction on a new target**, then regenerate that target’s census. Do not retroactively credit PR #225 to `c956c45e`.
5. **Repair the confirmed runtime gaps:** immutable prepared data, exact text-model identity checking, and enforced project/trust memory filtering. Add focused regression cases.
6. **Complete the semantic continuation frontier:** remaining files, alternate dispatch authority, provider-configuration drift, memory enforcement, terminal confinement, and identity-chain semantics.
7. **Run the existing fixtures and integration checks in an environment permitting isolated temporary files**, then obtain a separately recorded verifier approval before adding any release-certifying index entry.