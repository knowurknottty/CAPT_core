# ADR-0101 — Canonical schema language and schema versioning

**Status:** Accepted (M0-A)
**Date:** 2026-08-02
**Supersedes:** nothing
**Relates to:** spec §18, spec ADR-004, workflow §3

## Context

The CAPT Runtime Architecture Specification requires (invariant 14) that contracts be *language-neutral at the source* and generated for TypeScript and Python. The repository forensic baseline (`CAPT_RUNTIME_BASELINE_MAP.md` §3, rows 1–4) established:

- zero TypeScript files exist (`find . -name '*.ts'` empty);
- all 16,498 lines of existing Python define types as hand-written `@dataclass` with `asdict()` serialization;
- no schema file of any kind exists in the tree;
- the package has **zero runtime third-party dependencies** (`pyproject.toml` has no `dependencies` key).

Adopting the existing dataclasses as the contract source would make Python authoritative, contradicting invariant 14 and spec §18 ("TypeScript interfaces are reference views, not the sole normative definition" — the symmetric constraint applies to Python).

## Decision

**JSON Schema draft 2020-12 is the canonical, normative contract source.**

1. Schemas live under `contracts/schema/`, split by domain (`common`, `mission`, `task`, `policy`, `capability`, `tool`, `claim`, `evidence`, `verification`, `checkpoint`, `event`, `error`), with `contracts/schema/index.json` as the manifest.
2. Every schema file declares `$schema: https://json-schema.org/draft/2020-12/schema` and a `$id` of the form `https://contracts.capt.dev/<domain>/<Name>.schema.json`.
3. **Contract-set versioning** is a single monotonic string `CONTRACT_SCHEMA_VERSION` declared once in `contracts/schema/index.json` and propagated by the generator into both languages. M0-A ships `1.0.0`.
4. Every contract instance that is persisted or crosses a trust boundary carries a `schemaVersion` field constrained to `const: "1.0.0"` at this revision. Reader code rejects an unequal value (ADR-0110 defines the trust consequence).
5. Version bump rules: additive optional field → minor; any required field, enum member removal, discriminant change, or semantic change → major. A major bump requires a new ADR.

Rationale for JSON Schema over the alternatives is recorded below; the decisive factors were (a) `jsonschema` is already installed in the host environment and available on PyPI for CI, (b) it requires no compiler toolchain or code-gen binary to *validate*, so validation is possible even in a degraded/offline environment, and (c) it expresses discriminated unions via `oneOf` + `const` discriminants, which is the exact construct spec §18 and ledger Finding C demand.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| **Protocol Buffers** | Requires `protoc` plus per-language plugins in CI and on every contributor machine. The repository currently builds with setuptools and **no** external toolchain (baseline §7). Proto3 also cannot express closed discriminated unions with per-variant required fields without `oneof` + wrapper messages, and its JSON mapping loses the `const` discriminant guarantee. Rejected on toolchain weight and expressiveness. |
| **CUE** | Superior constraint language, but a single-vendor Go binary with no Python-native validator; would make validation impossible in the degraded offline mode the spec requires (invariant 15). Rejected. |
| **Smithy** | JVM toolchain. Rejected outright on dependency weight. |
| **TypeScript interfaces + `ts-to-json-schema`** | Makes TypeScript authoritative. Directly violates invariant 14 and ledger Finding O. Rejected. |
| **Python dataclasses + `pydantic`** | Makes Python authoritative; adds a heavy runtime dependency to a currently dependency-free package. Violates invariant 14. Rejected. |
| **Untagged/structural unions** | Rejected: ledger Finding C requires explicit discriminants so that validation cannot be bypassed by shape coincidence. |

## Consequences

**Positive**
- Neither implementation language is authoritative; a future Rust or Go component generates from the same source.
- Validation needs only `jsonschema` (Python) and a generated structural validator (TypeScript) — no build step required to *check* a payload.
- Discriminated unions are machine-checkable, satisfying ledger Finding C.

**Negative / costs**
- JSON Schema cannot express cross-field semantic invariants (e.g. "lease validity window must be inside grant validity window"). These must be encoded separately as executable invariants under `contracts/invariants/` and enforced in the runtime, not in the schema. This is an accepted, documented gap — see ADR-0107.
- `jsonschema` becomes a **test/CI** dependency. It is deliberately *not* added to `[project].dependencies`: the runtime imports generated code only, so the shipped package stays dependency-free.
- Hand-written generation (ADR-0102) is required because no off-the-shelf generator satisfies the reproducibility and no-new-toolchain constraints simultaneously.

## Reversal conditions

Revisit this ADR if any of the following becomes true:

1. Cross-field invariants exceed ~20 rules and duplicating them in three places (schema docs, Python, TypeScript) becomes the dominant source of drift → evaluate CUE.
2. Wire performance becomes a measured bottleneck (payloads > 1 MB or > 10 kHz) → evaluate Protobuf for the transport layer while keeping JSON Schema for the governance contracts.
3. A third implementation language is added and the hand-written generator exceeds ~1,500 LOC → evaluate a maintained generator.

## Evidence from the current repository

- `git ls-files | grep -c '\.ts$'` → `0`
- `pyproject.toml` — no `dependencies` key; `requires-python = ">=3.8"`
- `capt_solo/memory/models.py`, `capt_solo/foundry/registry.py:57` — dataclass-based type definitions with `asdict()`
- `python3 -c "import jsonschema"` → 4.25.1 present on host
- `.github/workflows/release-security.yml` — CI installs only `pytest pytest-cov build pip-audit`; no compiler toolchain
