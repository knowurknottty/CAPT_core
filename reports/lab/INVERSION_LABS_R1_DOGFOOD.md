# Inversion Labs CAPT R1 — Dogfood Evidence

**Status:** `DOGFOOD_EVIDENCE_CAPTURED_PENDING_FINAL_RECONCILIATION`
**Source head:** `819b94f30b97d18c64a61dea5e2db905a7df2d74`
**Frozen CAPT-core base:** `5f2917772e675523176a3112c49e28ffba20b8f1`

## Exact artifacts

- Retained wheel SHA-256: `7f065a6977b99bb42e98f389057da47a5193851b9060524b20c0c28cd3eadf9b`
- Retained sdist SHA-256: `a06f191357498302637b8560c91366b63db5e06335264a721a4e8cf2d5b7756f`
- Donor manifest digest: `sha256:dc86c8b8769f4cfba27e03e5d1c7edb460ee84b95a02f2b75673da39235a9d74`
- Native binary SHA-256: `852a7e242f440f56e16366a87b96a50b1d889ae5975171789ab66267140bd5f8`
- Bundle ID: `com.inversionlabs.capt.lab` (Team `49FBXNL38U`)
- Separate Lab state: `~/.capt-inversion-labs`

The installed golden core remained pinned to `5f2917772e675523176a3112c49e28ffba20b8f1` / wheel `46f09fb0c2d914c292112689b99809e3fb63d030f06af7040550f801ba95d259` and its ledger file hash was unchanged during Lab installation.

## Test evidence

- Source-tree Python regression: **938 passed / 57 skipped / 12 deselected / 0 failed**.
- Retained-wheel Python regression from site-packages: **938 passed / 57 skipped / 12 deselected / 0 failed**. The eleven CLI source-layout tests were given a temporary `capt_cli.py` symlink pointing to the installed site-packages module; no worktree package was imported.
- Swift normal suite: **35 passed / 4 opt-in live skipped / 0 failed**.
- Swift live suite against the final separate Lab runtime: **4 passed / 0 failed** in 60.894 s.
- Original CAPTLang Math donor: **17 Rust tests passed**, `cargo check --all-features` passed.
- Focused Lab gates: Math 15; Analogy+Consensus 15; Forge 8; governed runtime 9; targeted authority/security/model/replay regression 55.

## Retained-wheel specialist dogfood

The final runs used a fresh authoritative mission/task and authenticated RuntimeService commands. Mission stayed `draft -> draft`; task stayed `pending -> pending`. Every exact replay returned `idempotent/duplicate` with no second DriverRun. No verification, ClaimGuard decision, task-success, or mission-completion promotion was observed.

| Engine | Class | DriverRun | Claim | Evidence | Promotion | Verification | Replay |
|---|---|---|---|---|---|---|---|
| math | `calculation` | `dr-lab-d7f8bab6014de93034942aa1` | `cl-lab-d7f8bab6014de93034942aa1` | `ev-lab-8bc7051123d4f1fdfa3815b0` | `proposed` | `none` | `idempotent` |
| analogy | `heuristic` | `dr-lab-1b8e8f84726361ae35faf003` | `cl-lab-1b8e8f84726361ae35faf003` | `ev-lab-5f786da63dfcbab8a30c04d4` | `proposed` | `none` | `idempotent` |
| consensus | `advisory` | `dr-lab-9acf091a15b789b47db4d66d` | `cl-lab-9acf091a15b789b47db4d66d` | `ev-lab-26eceec45bd51e01fd4289f9` | `proposed` | `none` | `idempotent` |
| forge | `advisory` | `dr-lab-09bed5829a851e2d03610a4e` | `cl-lab-09bed5829a851e2d03610a4e` | `ev-lab-70a88bf6614deff3ab5a8bee` | `proposed` | `none` | `idempotent` |

### Live observations

- Math: `{'conductor': 5, 'degree': 4, 'discriminant': '125', 'unitRank': 1, 'torsionOrder': 10}`
- Analogy: structural similarity `1.000000`, confidence `0.647862`, analogy `True`.
- Consensus: P(true) `0.570676`, P(false) `0.429324`, confidence `0.014461`, most likely `true`.
- Forge: admitted `['README.md', 'src/math.py', 'test_math.py']`; excluded `['.env', 'escape.txt']`; truncated `False`. The live fixture's `.env` and escaping symlink were not read.

## Signed native UI dogfood

The signed `Inversion Labs CAPT.app` performed a real local chat turn through Ollama: request -> bound approval -> human approval -> provider DriverRun -> observation -> task `awaiting_verification`. The same active mission/task was then used by the native **Labs** view for `lab.math/cyclotomic_summary`.

Native Lab result: DriverRun `dr-lab-7c0602fab86a6ef193eea7fe`, Claim `cl-lab-7c0602fab86a6ef193eea7fe`, Evidence `ev-lab-80239f47c2fffd35eab90702`. The UI visibly rendered **CALCULATION** and **UNVERIFIED**.

That UI run occurred on the same source head using the first exact-source install wheel `7af02a50f2f9d2d4526e3226070edade11f9ce05ab7bba2090ec959435ff3c47`. Its `lab.math` implementation digest `sha256:f9942206ecd26bcaf2cfc3cc94bd046aec3cf30b9f5be268f469aec945c85fbc` is **byte-identical** to the retained final wheel's engine implementation digest. After repinning the runtime, all four specialists and all four live Swift runtime tests were rerun against the retained final wheel.

A later macOS AX attempt to repeat the already-proven Labs button after repin did not deliver the Swift action despite the control reporting enabled. No DriverRun was created and it is **not counted as evidence**. `CAPTRuntimeClient.connect()` explicitly drops/reopens/re-authenticates the socket, and shutdown/rebootstrap/reconnect passed in the final live Swift suite.

## Session/security evidence

- Lab session cache: `~/.capt-inversion-labs/ui/native_sessions.enc`, mode `0600`.
- Plaintext searches for the native binding prompt and assistant token: **0 matches**.
- Keychain-backed Lab session key item: present under service `com.inversionlabs.capt.lab.native-session-cache`.
- Signed bundle verifies and satisfies its designated requirement as `com.inversionlabs.capt.lab`.

## What this evidence does *not* claim

Software tests and deterministic calculations do not validate every inherited scientific algorithm. Placeholder/unvalidated donor routines remain excluded. Lab outputs are observations/advisories until independent CAPT verification occurs. Public-release readiness is outside this R1 dogfood classification.
