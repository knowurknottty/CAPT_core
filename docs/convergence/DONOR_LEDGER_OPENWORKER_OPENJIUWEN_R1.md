# Donor Ledger — CAPT Donor Convergence R1 (full manifest: openWorker, openJiuwen, all donors)

- Mission: `docs/missions/CAPT_DONOR_CHERRYPICK_INTEGRATION_R1.json`
- Council: `council-capt-donor-convergence-r1-20260924` · Mission ID: `m-capt-donor-convergence-r1-20260924`
- Target: `/Users/knowurknot/.capt/worktrees/openworker-convergence-r1`, branch `feat/openworker-convergence-r1`
- Cohort sequence: qwen38-flash (1/3) → mimo26-flash (2/3) → glm53-flash (3/3, this pass)
- **Authoritative frozen matrix source**: cohort 2/3 staged artifact `~/.capt/staging/dr-capt-donor-mimo26-r3/provider-analysis-dr-capt-donor-mimo26-r3.md` (PromptDigest `sha256:c6a4d5ab…31145`, ResponseDigest `sha256:9d176ec7…2d6` in its header). That session froze all donor HEADs via `git ls-remote` and fetched license text at each frozen SHA. This ledger transplants that matrix and finalizes dispositions; it does not re-derive it.

## 0. Integrity note (r1 write-up)

An earlier draft of this ledger was persisted in a corrupted state (degenerative loop artifacts, lost rows). It was overwritten by this version. This note is retained for honesty; the corrupted draft was never committed.

## 1. Drift re-query (falsifiable experiment #1 from cohort 2/3)

Re-query donor HEADs and compare to the frozen matrix. Executed for the donor with live integration work:

| Donor | Frozen SHA (r3) | Live re-query 2026-09-24 | Result |
|---|---|---|---|
| gitleaks/gitleaks | `b58d3f102cf3a2c84cb7f923d05c25c9b1aed84b` | `git ls-remote HEAD` → `b58d3f102cf3a2c84cb7f923d05c25c9b1aed84b` | **NO DRIFT** |

Remaining 39 rows: not re-queried this pass (bounded budget; only the donor with live code transplanted this round was re-verified). Marked UNPROVEN-against-drift; re-query of the full set remains open follow-up.

Note: cohort 2/3 prose says "All 41 donor HEADs frozen"; the manifest lists **40** donors and the r3 table contains 40 rows. Count discrepancy recorded, not silently repeated.

## 2. Baseline donor (pre-manifest)

| Donor | Frozen SHA | License | Final disposition |
|---|---|---|---|
| andrewyng/openworker | `37a09360d1d99a34b19c07b35c429f9b0a56abb0` | MIT (© 2024 Andrew Ng) | **INTEGRATED** at `e8ee447`: `capt_runtime/openworker_compat/*` (attachments, readonly, session_facts, toolresult, url_guard, workspace_trust, basedir, clock, environment) + `tests/capt_runtime/test_openworker_compat.py`; full snapshot retained as git subtree `third_party/openworker/`. See `docs/OPENWORKER_CONVERGENCE.md`. |

## 3. Manifest matrix — 40 donors (frozen SHA + license from r3; dispositions finalized by cohort 3/3)

| Donor | Frozen SHA (r3) | License at SHA | Final disposition | Basis |
|---|---|---|---|---|
| jamiepine/voicebox | `51f49dea198384b4eb6087b72c17057c6eb1c1cd` | MIT | DESIGN_REFERENCE_ONLY | mechanism inspection UNVERIFIED; no capability gap demonstrated |
| dyad-sh/dyad | `eda8b5812543f86fa3c5684d7a296d76943a3b52` | Apache-2.0 | DESIGN_REFERENCE_ONLY | app-builder domain; UNVERIFIED fit |
| presenton/presenton | `768894c4655c6c6fd6ed4cf69501cc502a2c0b41` | Apache-2.0 | REJECT | presentation-server domain; no CAPT surface (r3 provisional, upheld) |
| invoke-ai/InvokeAI | `910aec84095a8fb8be4b0d868a83d8e328c166ad` | Apache-2.0 | DESIGN_REFERENCE_ONLY | media pipeline; Secure Intake boundary governs any future use |
| upscayl/upscayl | `a00d55fee90e0f9435d5eaa86e76700df8199af8` | AGPL-3.0 | REJECT (no code copy) | AGPL contagion vs MIT repo |
| Anil-matcha/AI-Youtube-Shorts-Generator | `de07f3a94a9ef0c4c55376cfa118141de62a3d43` | MIT | REJECT | tutorial-grade pipeline; no surviving mechanism (r3) |
| Anil-matcha/Open-Generative-AI | `ad36d7be90f3c259e3ad2b27f03ff8bf5c8d16ca` | MIT | REJECT | same basis (r3) |
| plausible/analytics | `8f3970104aa77aedf2395868028e337169616267` | AGPL-3.0 | REJECT (license + fit) | AGPL; web analytics not a CAPT surface |
| nocodb/nocodb | `abf300c1b9002e05b58e0daedcb7f6e4573c5d1a` | Sustainable Use License | REJECT | source-available terms; control-plane risk |
| caddyserver/caddy | `7ee4441f9261d649eed215f27331352c1ab5a746` | Apache-2.0 | DESIGN_REFERENCE_ONLY | Go TLS server; no Python transplant target |
| NVIDIA/garak | `8d1259ef310e4803cf5a4cc77267fdfdc24434ec` | Apache-2.0 | DESIGN_REFERENCE_ONLY (REIMPLEMENT later) | probe taxonomy valuable; needs offline-first re-architecture |
| trufflesecurity/trufflehog | `cd94550e3eb05d4bd30952883aaffaeea062a9c7` | AGPL-3.0 | DESIGN_REFERENCE_ONLY (no code copy) | AGPL; gitleaks covers the same need under MIT |
| gitleaks/gitleaks | `b58d3f102cf3a2c84cb7f923d05c25c9b1aed84b` | MIT (© 2019 Zachary Rice) | **CHERRY_PICKED → INTEGRATED** (this round) | see §4 |
| google/osv-scanner | `46891bfc09691fe30646299688c9abe364e3cef4` | Apache-2.0 | EXTERNAL_SERVICE_BOUNDARY | requires live OSV database; must cross ToolBroker with network lease |
| snyk/agent-scan | `4e8d20dba67916b2e837f108c1708f7c2049eaf3` | Apache-2.0 | EXTERNAL_SERVICE_BOUNDARY | repo identity at SHA UNVERIFIED beyond license text |
| getsops/sops | `86bc0b08c13b3db3496f85270f8c061e0120927a` | MPL-2.0 | DESIGN_REFERENCE_ONLY (copy caution) | envelope-encryption model documented, not copied |
| semgrep/semgrep | `56e04ee9581f76a2a1cfcdd806dd2d276851a39f` | LGPL (version UNVERIFIED) | EXTERNAL_SERVICE_BOUNDARY behind ToolBroker | live-rule engine; network/service boundary |
| appwrite/appwrite | `49431717bb09fd5b62f433105f0fc0e9228b23bb` | BSD-3-Clause (text observed) | REJECT | backend suite would rival CAPT control plane |
| openJiuwen-ai/jiuwenswarm | `b7a7c32564a98eb2033271ed93b7ad0124fc92c8` | Apache-2.0 | ALREADY_PRESENT (provisional) | CAPT cohorts/councils cover swarm orchestration |
| openJiuwen-ai/agent-core | `6786cbe958b03c456440927319a894e0692b6c6d` | Apache-2.0 | ALREADY_PRESENT (provisional) | RuntimeService/session core equivalent |
| openJiuwen-ai/agent-studio | `2716f2245d062cadee7f8e68fc908c1e2fafb579` | Apache-2.0 | REJECT | UI is never authority in CAPT |
| openJiuwen-ai/deepsearch | `ff243bca4ab409116476587dcb106cf526581804` | Apache-2.0 | DESIGN_REFERENCE_ONLY | search capability gated; requires governed network lease first |
| openJiuwen-ai/agent-infer | `ea34e35611ded89ac875c7e3d0939634d8c5b084` | Apache-2.0 | ALREADY_PRESENT (provisional) | provider/inference layer exists |
| openJiuwen-ai/sciencediscovery | `dec6c6863e2132e992fc478c52dcdb6a1c9cd567` | Apache-2.0 | REJECT | domain application, not substrate |
| openJiuwen-ai/agent-protocol | `79201fe4c1bd1c8696f3ef750004969a906ccfcb` | Apache-2.0 | DESIGN_REFERENCE_ONLY | IPC framing must not weaken CAPT's bounded framing |
| openJiuwen-ai/agent-memory | `9bf45fa4154fc448cbe6a126958c50b9f26a1685` | Apache-2.0 | ALREADY_PRESENT (provisional) | CAPT Memory Engine; equivalence UNVERIFIED in detail |
| openJiuwen-ai/jiuwensymbiosis | `b3ffefebfa1678c0406e6f0a42399ba0efc1692c` | Apache-2.0 | DESIGN_REFERENCE_ONLY (UNVERIFIED) | no mechanism inspection |
| openJiuwen-ai/agent-core-java | `2347d3863296f92846e53b61298627a8d5f2f0b2` | Apache-2.0 | REJECT | no Java runtime in CAPT |
| openJiuwen-ai/docs | `d79ee3abc4be84f3efb06fafab6f9d4845d7debf` | CC-BY-4.0 | DESIGN_REFERENCE_ONLY | attribution required for any text reuse |
| openJiuwen-ai/agent-runtime-java | `41e8543b190bb05ab84d3948b2c92da7f50cfe1c` | Apache-2.0 | REJECT | no Java runtime in CAPT |
| openJiuwen-ai/skillhub | `24b35cc5d9af8ece4a7f36dbc4cdb8a58c3e180c` | Apache-2.0 | ALREADY_PRESENT (provisional) | authored-skills system exists |
| openJiuwen-ai/agent-tools | `824a5170517104332d9358721286ce5178125794` | Apache-2.0 | DESIGN_REFERENCE_ONLY | tools must re-host behind ToolBroker; no bypass |
| openJiuwen-ai/agent-runtime | `34ed6e86b99fab9b3f07d9f063efc1692ab365d2` | Apache-2.0 | ALREADY_PRESENT (provisional) | RuntimeService authoritative |
| openJiuwen-ai/community | `3bec17f31101a19543d7207cac08922c4a940b91` | CC-BY-4.0 | REJECT | no code |
| openJiuwen-ai/CareerSim-BDCI26 | `f61c738c72e51b77298cc1c14c7c6ebf4b6c527d` | MIT | REJECT | no fit |
| openJiuwen-ai/model-router | `dd68ef0ad283efcd8de9f6585a5ed13187a3ffd2` | Apache-2.0 | ALREADY_PRESENT (provisional) | fallback features UNVERIFIED against CAPT provider layer |
| openJiuwen-ai/relay | `9de45970272cc6985334b14da116b9e159a7fce6` | Apache-2.0 | DESIGN_REFERENCE_ONLY | no authority bypass permitted |
| openJiuwen-ai/.github | `7eb5e78685822c5e36ba35f5635dea5de0e5216d` | **UNLICENSED (no license file at SHA)** | REJECT (no grant) | copying prohibited absent license |
| openJiuwen-ai/agent-dx | `1bc13f13bea03c97004f734a3929dbdfc014c53a` | Apache-2.0 | DESIGN_REFERENCE_ONLY (UNVERIFIED) | no mechanism inspection |

## 4. Accepted integration this round (cohort 3/3): gitleaks-derived provider-token redaction

**Donor:** gitleaks/gitleaks @ `b58d3f102cf3a2c84cb7f923d05c25c9b1aed84b`, MIT, © 2019 Zachary Rice.
**Form:** hand-adapted registry of 14 credential-shape regexes (upstream rule ids recorded per pattern) + CAPT-native additions (`sk-or-v1-` OpenRouter family; generic `sk-` family subsuming Anthropic/OpenAI keys). Not a wholesale config copy. Provenance header with frozen SHA + MIT notice retained in the adapted module.

**Closed gap (from r3 §5, previously BLOCKED):** CAPT redaction layers handled secret-named keys and generic long tokens but had **no provider-specific token patterns**; a bare provider key under a benign key name could traverse export paths.

**Surfaces wired (4):**
1. `capt_runtime/secret_patterns.py` — registry module (`CREDENTIAL_PATTERNS`, `find_credential_shapes`, `redact_credential_shapes`).
2. `capt_runtime/discovery/redaction.py` — registry runs first, family markers before generic heuristics.
3. `capt_runtime/flight_recorder.py` — registry applies to every string value in forensic bundles (tokens under benign keys cannot leave in clear text); digest strings deliberately preserved.
4. `capt_solo/memory/secrets.py` — 5 provider families added locally (deliberate: no `capt_solo→capt_runtime` import; module decoupling preserved).

**Tests:** `tests/capt_runtime/test_secret_pattern_registry.py` — 12 discriminating tests: registry/fixture bijectivity, per-family detect+redact, benign false-positive negatives, flight-bundle end-to-end (token under benign key must not leave the `.capt-flight` archive), discovery-layer coverage, memory-screen regressions, provenance-retention assertion. **Mutation check executed:** disabling one pattern (`github_pat`) fails 3 tests; restored → 12/12 green (pattern deletions are detectable, not vacuous).

## 5. Considered and rejected (cohort 3, with rationale)

- **Registry wiring into `capt_runtime/governed_composition.py` (`capability_world_digest`)**: REJECT. That surface computes a digest input, not an export surface; secrets are omitted by key (`{"redacted": True}`) and credential references hashed by design. Hashing is not disclosure. Registry substitution there would churn composition digests for marginal gain.
- **`security_gate.py` VIBE1-01/02 "secret scan" hints**: REJECT for this round. That module is a verification-catalog evaluator; the catalog intentionally describes *what evidence a release must supply* (e.g. a gitleaks run is operator-supplied evidence) — it does not execute scans. Wiring an internal scanner into the catalog would conflate "control exists" with "evidence verified", weakening fail-closed semantics. The registry now gives operators a local scan primitive to satisfy that evidence.
- **openJiuwen ALREADY_PRESENT rows**: held provisional (r3 status); no mechanism inspection performed this round beyond cross-checking that the named CAPT counterparts exist (RuntimeService, Memory Engine, cohorts/councils, authored skills, provider layer). Semantics equivalence remains UNPROVEN; labels in §3 keep "(provisional)".

## 6. Verification gates executed (cohort 3/3, 2026-09-24)

| Gate | Result |
|---|---|
| Targeted: `pytest tests/capt_runtime/test_secret_pattern_registry.py` | **12 passed** (venv `~/CAPT_core/.venv/bin/python`, 3.12.13) |
| Full suite: `python -m pytest -q` | **1573 passed, 18 skipped, 13 deselected, 0 failed** (~70 s) |
| Contract drift: `python3 contracts/tools/check_drift.py` | **OK — 11 generated files match schema source** |
| `git diff --check` | **clean (exit 0)** |
| Mutation discriminability (registry pattern disabled) | 3 tests fail → restored → green (discriminating, not vacuous) |
| Donor SHA drift re-query (gitleaks) | NO DRIFT vs frozen matrix |
| Full 40-donor SHA re-query | NOT EXECUTED this round — UNPROVEN-against-drift (open follow-up) |
| Push / merge / publish | NOT PERFORMED (per mission invariants) |

Environment notes (honesty): system `python3` is 3.9 and cannot collect the suite (`datetime.UTC` missing) — interpreter `~/CAPT_core/.venv/bin/python` (3.12.13) used; with system-pythons, 25 failures were all `ModuleNotFoundError: textual` (dependency absent in those environments, not a code defect).

## 7. Remaining open items (explicit, not silently dropped)

1. 39-donor SHA drift re-query (mechanized; assert-equal against §3).
2. Mechanism inspection for donors dispositioned UNVERIFIED/provisional (≈38 donors) — dispositions rest on license + domain + CAPT-inventory reasoning.
3. snyk/agent-scan identity at frozen SHA; semgrep LGPL version.
4. sops-style at-rest envelope encryption for CAPT state (design-reference; MPL copy caution).
5. garak probe taxonomy reimplementation (offline, stdlib-first) — r3 flagged "REIMPLEMENT later".
6. openJiuwen router fallback / memory recall feature-diff to convert provisional ALREADY_PRESENT labels into verified or corrected dispositions.

All claims above are traceable to: this worktree's uncommitted diff (redaction integration), the full-suite run recorded in §6, and the staged r3 artifact named in the header. Nothing in this ledger asserts CAPT approval, verification IDs, or ledger events beyond those artifacts.