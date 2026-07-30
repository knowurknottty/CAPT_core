# RUNTIME_ADAPTER_READINESS_REVIEW

Generated: 2026-07-30. Audit target: integration HEAD `716ecc9`. Question: is
the Treasure Chest provider-neutral runtime adapter (doc 15 Workstream E)
present, Hermes-coupled, or absent?

## 1. Where inference actually happens today

There is exactly ONE model-runtime touchpoint in core: `capt_solo/pulse.py`
(`PulseGateway.complete/chat`). It is:
- disabled by default (`enabled` returns False unless configured);
- lazily importing `urllib.request` ONLY inside `complete()`/`chat()`;
- never imported at module load (verified: no top-level network import);
- not imported by any other module (grep: zero `from capt_solo.pulse` /
  `import pulse` outside tests).

Everything else (memory, CTP, evidence, verification, knowledge, contextpack,
foundry, governance, release validation) is pure local logic. Confirmed today
by a socket-deny import test in a clean venv with Hermes NOT installed:
`import capt_solo` + all core subpackages → no network, no Hermes. This
satisfies TC-RUNTIME-003 (core imports/operates without Hermes) and the
doc 15 §E requirement "Memory, CTP, proof, governance, Spaces, release
validation must work with no model runtime configured."

## 2. Hermes coupling — precise

| Surface | Coupling | Verdict |
|---|---|---|
| Core code (`capt_solo/*` except plugin) | ZERO `import hermes`; ZERO hard dependency | Clean |
| `capt_solo/plugin/__init__.py` | Inbound Hermes plugin: stateless wrappers exposing CAPT public API TO Hermes; `provenance="hermes"` default on records | Inbound only; Hermes is a CONSUMER of CAPT, not a dependency |
| `capt_solo/foundry/harness.py` | Command allowlist regex includes `capt-solo|python|hermes` as a SAFE prefix | Cosmetic; not an import |
| `pyproject.toml` dependencies | `["pyyaml>=5.4"]` | No Hermes, no httpx, no openai, no anthropic |

Conclusion: **CAPT can install and operate without Hermes** (proven). Hermes
is one integration, not the architecture. TC-RUNTIME-006 (Hermes as one
adapter, not dependency) is PARTIALLY satisfied — the architecture is clean,
but there is no outbound adapter layer to demonstrate the claim operationally.

## 3. Existing runtime abstractions (reuse, don't rebuild)

- `capt_solo/research/adapter.py`: `ResearchAdapter` (Protocol-ish base),
  `LocalFallbackAdapter`, `ResearchAdapterRegistry` (register/get/fallback).
  This proves the registry pattern works in-tree and is the closest precedent
  for the required `AdapterRegistry`. Scope is research-task execution, not
  model generation — but the contract shape (registry + fallback + status) is
  directly reusable.
- `pulse.py` `PulseGateway`: the actual generation seam, but single-impl and
  not behind a registry.

## 4. Current architecture vs required contract

Required (doc 15 §E): adapter identity, provider/model identity, request/
response provenance, generation, streaming, tool calls, structured output,
multimodal, limits, cancellation, usage, refusals, retry policy, network/
secret requirements, local-vs-remote. Registry: register/unregister/list/get/
health/select; selection respects Space policy.

| Required element | Today | Gap |
|---|---|---|
| Generation seam | `PulseGateway` (single) | Needs to become one of N adapters behind a contract |
| Adapter identity / registry | research registry (precedent) | New `capt_solo/adapters/` registry for model-runtime adapters |
| Provider/model identity | none | New |
| Provenance on requests/responses | partial (provenance field on records) | Extend to adapter calls |
| Streaming/tool calls/structured/multimodal | none | New (can be optional in v1 contract) |
| Limits/cancellation/usage/refusals/retry | none | New (can be optional) |
| Local-vs-remote + secret requirements | pulse has endpoint+enabled | Formalize as adapter metadata |
| Two proven paths | only pulse (one impl) | Need a second: a direct/local non-Hermes adapter (e.g. a local stub or a second provider) to PROVE neutrality |

## 5. Proposed neutral contract (design-only)

```
capt_solo/adapters/
  contract.py   # RuntimeAdapter Protocol (normalize the doc 15 fields)
  registry.py   # AdapterRegistry: register/unregister/list/get/health/select
  local.py      # LocalFallbackAdapter (no network; deterministic for tests)
  pulse_adapter.py  # wraps PulseGateway behind the contract
  hermes_adapter.py # wraps plugin outbound calls behind the contract (future)
```

Selection: `registry.select(space_policy)` returns the highest-priority
healthy adapter allowed by Space policy (local-only, allowlists, fallback
order). `core` calls `registry.select(...).generate(...)` instead of
`PulseGateway` directly.

## 6. Proof requirements (doc 15 §E, mandatory before claiming neutrality)

1. Direct/local non-Hermes adapter executes a generation end-to-end with
   network denied (the `LocalFallbackAdapter` + socket-deny test pattern).
2. Hermes adapter (or a second provider) executes behind the SAME contract.
3. `core` imports and runs with NO adapter configured (already true today).
4. Space policy `local-only` rejects remote adapters (needs Spaces — see
   SPACE_READINESS_REVIEW; this proof is deferred to v0.5.1 with Spaces).

## 7. Recommendation

Adapters are NOT required for a truthful v0.5.0: the current public claim
"model-agnostic architecture; no harness dependency" is EVIDENCED today
(zero hermes imports, proven import test). The adapter CONTRACT should be
drafted in v0.5.0 as a Provisional, unproven seam ONLY IF owner wants the
public architecture to show the seam — but the two-path PROOF belongs to
v0.5.1 (with Spaces, since policy selection depends on Space). Implementing
adapters before Spaces risks a second overlapping abstraction and an
unprovable claim. Keep Hermes inbound-only; do not make it a mandatory import
anywhere (STOP CONDITION per mission: implementation must not make Hermes
mandatory).
