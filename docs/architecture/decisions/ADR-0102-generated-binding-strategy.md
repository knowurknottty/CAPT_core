# ADR-0102 — Generated TypeScript and Python binding strategy

**Status:** Accepted (M0-A)
**Date:** 2026-08-02
**Relates to:** ADR-0101, spec §18, workflow Gate 2

## Context

ADR-0101 makes JSON Schema 2020-12 canonical. Workflow Gate 2 requires that bindings:

- carry a non-editable header;
- regenerate reproducibly from a clean checkout;
- behave equivalently across languages for shared fixtures;
- fail CI on drift;
- expose typed discriminated unions rather than pervasive `unknown`/`Any`;
- isolate extension payloads behind explicit namespaces.

Baseline §7 constrains the solution: the host default interpreter is **Python 3.9.6**, CI runs **3.10 and 3.12**, and `ruff`/`mypy`/`black` are not installed. Node 22 and `tsc` 6.0.3 are available and a `tsc --strict` → `node` round trip was proven working (exit 0).

Off-the-shelf generators were evaluated against these constraints and all failed at least one: `datamodel-code-generator` emits Pydantic (new heavy dependency, ADR-0101 rejects), `quicktype` requires a Node install step in the Python CI job and does not emit closed discriminated unions with runtime validators, `json-schema-to-typescript` emits types only with no runtime validation, giving no cross-language behavioural parity.

## Decision

**A single hand-written, deterministic generator — `contracts/tools/generate.py` — emits both languages from `contracts/schema/`.**

1. **One generator, one traversal.** Python and TypeScript emitters consume the same in-memory schema model, so a schema construct cannot be interpreted differently per language by construction.
2. **Determinism requirements.** The generator: sorts every mapping by key before emission, never emits a timestamp, never emits a hostname, path, or username, never depends on filesystem iteration order (`sorted(Path.glob(...))`), and derives its header digest from schema content only. Consequence: two runs on different machines at different times produce byte-identical output.
3. **Header.** Every generated file begins with a machine-checkable header containing `DO NOT EDIT`, the generator path, the command to regenerate, `CONTRACT_SCHEMA_VERSION`, and `source-digest: sha256:<hex>` computed over the canonicalized schema set.
4. **Python emission target: 3.8+ syntax.** `from __future__ import annotations`; `typing.Optional[X]`/`typing.Union[...]` rather than `X | Y`; no `match`; frozen `@dataclass`es; `Literal` discriminants; `Enum` for closed value sets. Validated by `compileall` on 3.9 and 3.12.
5. **TypeScript emission target: ES2022 + `--strict`.** `readonly` interface fields; string-literal-union discriminants; `as const` enum objects; discriminated unions as `type X = A | B | ...` narrowed by the discriminant property.
6. **Runtime validators in both languages.** The generator emits `validate_<Name>()` (Python) and `validate<Name>()` (TypeScript) implementing the *same* checked rules: required fields, type, enum membership, discriminant match, pattern, min/max, `additionalProperties: false`, and extension-boundary rules. Both return a normalized, sorted list of `path: message` errors so parity can be asserted **on error text**, not just on accept/reject.
7. **Drift detection.** `contracts/tools/check_drift.py` regenerates into a temporary tree and compares byte-for-byte against the committed tree, reporting per-file first-difference. Non-zero exit on any difference. Wired into CI (ADR-0111 lists CI scope).
8. **No `Any`/`unknown` in generated types** except inside the single extension envelope (`ExtensionEnvelope`), which is itself schema-constrained: `namespace` must match `^x-[a-z0-9]+(\.[a-z0-9]+)*$`, `payload` must be a JSON object, and the envelope is only permitted where a schema explicitly references it.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| `datamodel-code-generator` | Emits Pydantic v2 → heavy runtime dependency in a currently dependency-free package; no TypeScript emitter, so a second tool (and second interpretation of the schema) would be required. |
| `quicktype` | Node-only; would force Node into the Python CI job. Emits no closed discriminated-union validators; `additionalProperties: false` handling is inconsistent. |
| `json-schema-to-typescript` + `jsonschema` (Python) | Types-only on the TS side ⇒ no runtime validator ⇒ cross-language *behavioural* parity is unprovable. Two independent tools = two schema interpretations = silent divergence. Rejected. |
| Two independent hand-written generators | Doubles the interpretation surface; guarantees eventual divergence. Rejected in favour of one traversal, two emitters. |
| Generate at import time (no committed artifacts) | Makes drift undetectable, breaks the "generated files clearly state they are generated" requirement, and makes the TypeScript package unusable without Python. Rejected. |

## Consequences

**Positive**
- Byte-stable, reviewable, diffable artifacts; drift is a hard CI failure.
- Zero new runtime dependencies in either language.
- Cross-language parity is testable at error-message granularity.

**Negative / costs**
- The generator supports only the JSON Schema subset CAPT actually uses. Unsupported keywords must fail loudly (`UnsupportedSchemaError`) rather than be silently ignored — otherwise a schema author could believe a constraint is enforced when it is not. This is implemented and tested.
- Adding a schema keyword requires a generator change plus tests in both languages.
- The generator is CAPT-maintained code and carries its own defect risk; mitigated by fixture round-trip tests and negative fixtures.

## Reversal conditions

1. Generator exceeds ~1,500 LOC or the supported keyword subset exceeds ~25 keywords → re-evaluate a maintained generator with a vendored, pinned toolchain.
2. A third target language is required → re-evaluate.
3. A maintained generator appears that emits dependency-free dataclasses **and** TypeScript **and** matching runtime validators → migrate.

## Evidence from the current repository

- Baseline §7: host `python3` = 3.9.6; CI matrix = 3.10, 3.12 → `X | Y` runtime syntax is unsafe.
- Baseline §7: `tsc` 6.0.3 available; `tsc --strict` + `node` round trip verified exit 0.
- `pyproject.toml`: no `dependencies` key — the zero-dependency property is a real, current property worth preserving.
- `.github/workflows/release-security.yml`: `compileall` and grep-based invariants are the existing precedent for lightweight, toolchain-free static gates.
