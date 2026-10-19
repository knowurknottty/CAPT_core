# CAPT Core technical manual — architecture and authority boundaries

> **Original source scope:** `knowurknottty/CAPT_core` at `0d8e46d095243e80febd4e30f5ae52c9202316d9` (2026-10-18); an additional [source/test delta review](CURRENT_HEAD_DELTA.md) covers the later pinned `c956c45e` (not subsequent main) and does not automatically upgrade every section in this manual. **Evidence status:** source cross-reference and selected tests, **not** a complete RRDS-1 deep review or live-provider/release certification. This manual consolidates entry points into existing source and canonical references; detailed contracts remain authoritative.

## 1. System purpose and trust boundaries

CAPT is a local-first, governed continuity/runtime system in which a model is replaceable and its output does not constitute an authoritative operational record. CAPT distinguishes command admission, scope and approval, effect execution, observed result, evidence admission, verification, and completed state.

```text
Human/operator
      |
CLI / TUI / desktop / approved integration
      |
      v
RuntimeService (command and query boundary)
      |
      +-- governance / HumanApproval / capability and leases
      +-- EventStore and authoritative state projections
      +-- memory / context assembly
      +-- evidence / verification / ClaimGuard boundaries
      |
      v
DriverHost / ToolBroker / provider adapters
      |
      v
External/local models and bounded tools
      |
      v
Untrusted result or artifact candidate
      |
      +--> governed evidence admission -> verification -> allowed completion
```

The diagram is conceptual, **not** a guarantee that every integration or release path is connected. The actual command/effect boundaries must be verified for a particular workflow. See [Architecture](ARCHITECTURE.md), [Governance](GOVERNANCE.md), and [Current state](CURRENT_STATE.md).

## 2. Authoritative components in source

| Concern | Primary source | Boundary to respect |
|---|---|---|
| Runtime coordination | [`capt_runtime/services.py`](../capt_runtime/services.py) (`RuntimeService`) | Model/UI clients do not write authoritative state independently |
| Durable events | [`capt_runtime/store.py`](../capt_runtime/store.py) (`EventStore`) | Avoid ad hoc direct SQLite/filesystem mutations |
| Approval aggregate | [`capt_runtime/aggregates/human_approval.py`](../capt_runtime/aggregates/human_approval.py) | Authorization is scoped; not equivalent to execution/completion |
| Driver boundary | [`capt_runtime/driver_host.py`](../capt_runtime/driver_host.py) | A driver result needs appropriate admission and verification |
| Bounded tool execution | [`capt_runtime/tool_broker.py`](../capt_runtime/tool_broker.py) | Tool authority is not provided by the model or an adapter alone |
| Standalone memory | [`capt_solo/memory/engine.py`](../capt_solo/memory/engine.py) | Solo memory is separate from governed RuntimeService memory |
| CLI argument contracts | [`capt_cli.py`](../capt_cli.py) | Installed help is authoritative for that installed version |
| Package commands / deps | [`pyproject.toml`](../pyproject.toml) | Package name/version are not full system release status |

For public schema details, use [Data model](DATA_MODEL.md) and [API reference](API.md); the latter is generated from the installed package and must be regenerated using its documented generator if signatures change.

### Current-HEAD Bot and bioCAPT integration boundaries

The pinned source also contains [Core Bot identity aggregate](../capt_runtime/aggregates/bot.py), [governed Bot registration](../capt_runtime/governed_service.py), the [Bot manifest schema](../contracts/schema/bot.schema.json), and a native [Bot Browser view](../capt_ui/surfaces/desktop_swift/Sources/CAPTNativeMac/Views/BotBrowserView.swift). These demonstrate source-present identity and UI boundaries, **not** a deployed autonomous Bot. The separate [CAPT-Bot repository](https://github.com/knowurknottty/CAPT-Bot) still describes R5 convergence onto current Core as an unfinished release gate.

An optional [bioCAPT cohort reader](../capt_runtime/biocapt_cohort_reader.py) enforces live grants/leases and local socket constraints. [Runtime startup registration](../desktop/capt_runtime_service.py) is explicitly opt-in. Selected targeted tests passed, but real bioCAPT deployment and end-to-end execution remain unproven. See [current-HEAD delta evidence](CURRENT_HEAD_DELTA.md).

## 3. Executable surfaces

- **`capt`** — primary CLI. `start`, `status`, `stop`, `checkpoint`, `resume`, `doctor`, `evidence`, `run`, `tui`, `memory`, `skills`, and `harness` are declared in `capt_cli.py`.
- **`capt-ui`** — operator CLI; `dashboard` prints a summary, while `capt tui` launches the interactive Textual surface. Details: [CLI](CLI.md), [TUI](TUI.md).
- **`capt_solo.api`** — in-process Solo APIs, distinct from the RuntimeService/Harness command boundary. Details: [generated API](API.md), [plugin guide](PLUGIN_GUIDE.md).
- **Native macOS target** — source under [`capt_ui/surfaces/desktop_swift`](../capt_ui/surfaces/desktop_swift/). A successful source build is not proof of signed distribution; see [Desktop](DESKTOP.md).

## 4. State locations and storage semantics

| State class | Default / override | Key distinction |
|---|---|---|
| Canonical local runtime state | `~/.capt` / `CAPT_STATE_DIR` | Runtime service socket/token/ledger paths are environment- and lifecycle-sensitive |
| Standalone Solo memory | `~/.capt-solo` / `CAPT_SOLO_HOME` | `capt memory store/search` writes and reads Solo memory, not automatically RuntimeService ContextPack |

These paths are documented in [Installation](INSTALLATION.md) and CLI source. They can contain private data. **Do not upload, paste, or commit tokens, ledgers, personal memories, provider configuration secrets, or raw diagnostic bundles** to get help.

## 5. Governed command and tool lifecycle

A trustworthy implementation trace should answer:

1. **Entry point:** what request/command was accepted, by whom, at which revision?
2. **Authority:** which policy, capability/lease, and approval governed the attempted action?
3. **Effect:** did a driver/tool execute; what exact endpoint or resource scope was authorized?
4. **Witness:** which durable event/receipt, artifact digest, and verifier establish the outcome?
5. **Completion:** which runtime decision allowed a task/mission to transition state?

Absent evidence is an **unknown**, not a license to mark success. When an external action might have occurred but its result is unknown, reconcile before retrying; idempotency keys constrain specific calls but cannot erase uncertainty at all external effect boundaries.

See [Governance](GOVERNANCE.md), [Proof engine](PROOF_ENGINE.md), [ClaimGuard](CLAIMGUARD.md), and [Review/verifier contract](workflows/CAPT_REVIEWER_VERIFIER_CONTRACT.md).

## 6. Models, providers and media

Provider discovery/health, fixture-backed adapter behavior, authorized external inference, and a release-certified user workflow are distinct claims. Provider use may incur network transmission, authentication requirements or charges. Do not dispatch live generation simply to validate a documentation example.

The source tree contains governed media work and native file staging, but **staging a file is not the same operation as transmitting it to a model**. Consult [Providers](PROVIDERS.md), [Model providers](MODEL_PROVIDERS.md), and the date-scoped [media R2C note](GOVERNED_MULTIMODAL_R2C_FILES_2026-10-08.md) for exact gates and limits.

## 7. Failure and recovery model

Common cases include runtime not running, insufficient authority, stale/digest-mismatched approval, provider unavailable, uncertain tool dispatch, replay conflict, and incomplete verification. Appropriate responses differ: reconfigure safely, request approval, inspect evidence, or reconcile an uncertain effect; never indiscriminately replay a potentially consequential action.

`capt checkpoint` and `capt resume` exercise runtime recovery boundaries. A simple restart is **not** an end-to-end proof of workload restoration or no-repeat tool effects. See [Troubleshooting](TROUBLESHOOTING.md), [User guide](USER_GUIDE.md), and [Release evidence](RELEASE_EVIDENCE.md).

## 8. Verification and development

At the pinned checkout, the declared package is `capt-solo 0.5.0`, requiring Python `>=3.8` per metadata. Exact installed compatibility must be tested per target environment.

Read-only CLI introspection:

```zsh
capt --version
capt --help
capt status --help
```

Selected developer checks, from the root with test dependencies installed:

```zsh
python -m pytest -q tests/test_api_reference.py tests/test_capt_repo_audit_gate.py
```

**Receipt:** on 2026-10-18, using the checkout's `.venv/bin/python` (Python 3.12.13), these two test modules reported **10 passed in 0.75s**. The test result applies to those modules in that checkout, not to a full runtime integration, independent verifier, or release gate.

Deep repository review must follow root [`AGENTS.md`](../AGENTS.md) and [RRDS-1](workflows/CAPT_REVIEWER_VERIFIER_CONTRACT.md): a recursive census, file/line receipts, the audit gate, and an independent verifier. No such full review is claimed by this manual.

## 9. Canonical references and boundaries

[CLI](CLI.md) · [API](API.md) · [Architecture](ARCHITECTURE.md) · [Data model](DATA_MODEL.md) · [Governance](GOVERNANCE.md) · [Security](SECURITY.md) · [Validation](VALIDATION.md) · [Release evidence](RELEASE_EVIDENCE.md) · [Glossary](GLOSSARY.md)
