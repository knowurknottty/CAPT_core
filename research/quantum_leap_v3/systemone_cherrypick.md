# System One Harness → CAPT Core: cherry-pick audit and bounded adaptation

**Date:** 2026-10-19 (CDT).
**CAPT review target:** `knowurknottty/CAPT_core` @ `e28b66504c422946a66409d0de12e71f1646aae6`.
**Donor:** `HarnessRouter/SystemOneHarness` @ `ab8e8f08b4a6268c0633a474423d556599ee06a4`.
**Donor metadata:** `pyproject.toml` version 0.4.0; Apache License 2.0.
**Local checkout:** `/Users/knowurknot/capt-node-workspace/quantum-leap-donors/SystemOneHarness`.
**Review:** partial architectural/code review, targeted source spans, local tests. Not an RRDS-1 whole-repository audit, not an independent reproduction of the donor's published Jev benchmarks.

## Thesis

The donor's crucial inversion is that a decision model does **not** write commands. An environment enumerates allowed options, parameter domains and state; a model chooses among the options, returns probabilities, and the harness gates the result. CAPT already has an authoritative ToolBroker/RuntimeService/EventStore. The valuable transfer is a **narrow, capability-filtered observation/proposal interface** into those boundaries—not the donor's execution controller or authorization semantics.

Keep **model probability**, **proposal feasibility**, **current authority**, **observed effect**, **content verification**, and **mission completion** as distinct, separately evidenced properties. Their conflation is the largest risk.

## Source-grounded shortlist

| Candidate | Donor evidence | CAPT analog | Decision |
|---|---|---|---|
| Finite typed action-space compiler | `systemone_harness/actions.py:39-103,132-228,240-256` supports fixed choices, observation candidates, flags, levels; rejects free text | ToolBroker admission, model approval binding, ContextSlice; no unified decision action-space compiler found at pin | **P0: adapt as a bounded *proposal* interface**, not execution |
| Explicit omissions | `actions.py:167-228` records disabled/missing-candidate actions | CAPT refusal and gate reasons, `gate_result.py` (present, explicitly not integrated) | **P0: adapt** so the model and operator can distinguish absence/denial/unknown |
| Probability-aware abstention and structured handoff | `gate.py:34-69`, `controller.py:125-134,165+`, `trace.py:13-60` | Council confidence, continuation context, existing calibration/loop detector (not live proof) | **P0/P1: adapt as advisory, receipted escalation**; never grant rights |
| Full decision distribution and model identity | `trace.py:13-33,95+` | DriverRun receipts, provenance, PAL concept | **P1: store bounded, redacted distributions** only with explicit purpose and data-retention policy |
| Versioned config and objective-based outer calibration loop | `config.py`, `objective.py`, `docs/dual-loop.md:73-135` | governance fixpoint, interventional ledger, model succession, Learning Plane interface | **P1: experiment** one parameter/change at a time on a frozen, independent outcome oracle |
| MCP tool schemas → finite actions | `envs/mcp.py`, `tools.py` | existing CAPT Node/Workspace MCP services | **P1: selectively compile a *trusted allowlist***, not raw arbitrary server schemas |
| Unified Harness Protocol surface | `uhp.py` and donor conformance report | CAPT existing runtime and API surfaces | **P2: defer** until interoperability value exceeds new attack surface |
| Drop-in model/controller/realtime/browser loop | `controller.py:55-158`, `envs/browser.py` | CAPT RuntimeService, drivers, ToolBroker, TIA | **REJECT wholesale transplant**; would create a competing authority and uncertain effects |

## Two donor behaviors CAPT must reject

1. **Completion without independent proof.** `controller.py:112-121` returns `completed/finish_insisted` after two model `finish` selections while goal probability is still low. `trace.py:70-77` preserves that status. CAPT should emit `VERIFY` or `INCOMPLETE`, never `TASK_COMPLETED`, without an independent outcome receipt.
2. **Threshold bypass on real-time reads.** `controller.py:91-97` upgrades a low-confidence refused read into a `run` for realtime environments. A read can still disclose secrets or consume a paid API call, and a declared `read` label does not establish CAPT authorization. Do not import this bypass.

Additional cautions: `gate.py:34-69` applies confidence thresholds but does not enforce CAPT capabilities; guard questions in `actions.py:223-225` are not by themselves verified side conditions. `encoder.py:30-100` drops context fields by a budget heuristic, not by a confidentiality proof. `envs/mcp.py:153-159` directly calls MCP tools after coercion; that must never bypass RuntimeService admission, target-version checks, budgets or reconciliation. The donor's action-risk classification cannot be inherited from untrusted model text or unverified MCP metadata.

## Local source and test evidence

The public donor was cloned to a separate, clean worktree, with `git rev-parse HEAD` = `ab8e8f08...` and 54 tracked files. Inspected architecture, dual-loop design, actions, controller, gate, encoder, environment, trace, configuration, objective, and MCP adapter source; CAPT's pinned Tree, gate, governance, learning, and tool-broker symbols were searched.

`python3 -m pytest -q tests` produced **42 passed, 2 failed, 2 skipped**. The two failed cases require the optional MCP client import `mcp.client.client.Client`, which is absent in the selected macOS Python environment. This establishes a local dependency/compatibility blocker; it is not an end-to-end validation of the donor's MCP implementation. No donor code, APIs, keys or provider endpoints were used in CAPT.

Donor's published success on small order scenarios and UHP core conformance remains **donor-reported evidence**, not independently replicated in this investigation. No live Jev inference, calibration, latency, cost or alternative model benchmark was performed.

## Cherry-pick implemented in the *isolated research branch*

An original, independent implementation exists in `research/quantum_leap_v3/finite_decision.py`. It is **not** imported from or wired into production CAPT.

The **proposal compiler**:
- consumes explicit registered actions, a policy-provided observation scope and finite candidate values;
- accepts finite `enum`, `candidate`, `boolean` and ordered `levels` parameters;
- refuses free-text parameters, unknown/missing risk classes, duplicate/oversized choices and malformed declarations with explicit omission reasons;
- accepts only opaque `h_<32 lowercase hex>` candidate references rather than arbitrary source text;
- binds the compiled offering to separately supplied 64-character world and policy SHA-256 digests;
- rejects invalid/NaN/out-of-range action and parameter probabilities, values not offered, stale offering digests and weak option probabilities;
- reports `proposal_ready_for_runtime_review`, `needs_escalation`, `verification_required`, `escalation_requested` or `refused`;
- **always sets `dispatch_allowed=false` and `completed=false`**.

This prototype is intentionally not a model adapter, not a functioning CAPT RuntimeService integration, and not a privacy or consent guarantee. The world/policy digests are caller-supplied and have **not** been authenticated by RuntimeService. The confidence values are uncalibrated for actual CAPT workloads; a model could report arbitrary high probabilities. The opaque-handle policy is only a bounded interface rule; it does not prove end-to-end confidentiality.

**Verification:** `test_finite_decision.py` — 22 isolated deterministic tests pass. The two prior Quantum Leap suites remain separate and must also pass before branch promotion.

## Adjacent Quantum Leap progress: shadow-only debt ratchet

`shadow_ratchet.py` reads `phase2_results.json` and checks longitudinal fidelity/identity invariants over the same 52-claim set. It computes a *proxy*, not semantic certainty debt:

`D_proxy = number of claims not labeled full-fidelity WITHIN`.

`3f11800 -> e28b665`: **19 -> 20**, sole newly unconfirmed `PU7` (87 → 88 modules). Advisory result: **`WOULD_PAUSE_FOR_REVIEW`**. Hard-coded `runtime_release_authorized=false`, `semantic_verification=NOT_ASSESSED`. It is not a real merge/release/learning gate and has no CAPT runtime integration.

`test_shadow_ratchet.py`: **8 tests passed** over actual stored evidence, including population/fidelity mismatch refusal, invariant refusal and overwrite protection. Evidence: `shadow_ratchet_result.json`.

## Design synthesis: Decision-Sufficient Inspection corridor

```text
Pinned environment / world snapshot (truth source)
  ↓ locally enumerate policy-visible opaque actions + bounded parameters
Finite Action Compiler (decision offering + omissions + snapshot/policy digest)
  ↓
Model decision with full probability vector (untrusted suggestion)
  ↓
Advisory Confidence / Refusal / Escalation assessment
  ↓
CAPT RuntimeService *fresh* authority + exact plan/identity checks
  ↓
ToolBroker prepare / admit / dispatch / settle / reconcile
  ↓
Independent world probe / verifier / receipt (Executable Beliefs)
  ↓
Certainty Debt accounting + truthful completion gate
```

The corridor makes the **model weaker as an authority but potentially more useful as a fast policy selector**. Jev-class models would be optional, governed proposer seats. Any claim that this changes latency, provider spending or error rates requires paired production-representative measurement.

## Go/no-go gates before actual cherry-pick into CAPT authority

1. **Semantic mapping:** independent adjudication of content claims to predicates (the original 52 claim verdicts are not enough). Include paired negative worlds where the predicate holds but prose is false.
2. **Authority invariants:** prove the runtime—not the compiler or MCP server—owns action registration, risk class, grants, nonce, budgets, observation digest and identity binding.
3. **Replay/versioning:** stale world/policy/target refusal and delayed/revoked authority tests, including an intervening external write.
4. **Disclosure:** map opaque handles to private objects locally; test outbound contexts and logs; prevent adaptive predicate probing from leaking protected distinctions.
5. **Decision calibration:** compare weakest-confidence and abstention rules against a no-model/local-rules baseline and a provider-plus-timeout baseline. Report Brier/ECE, precision, recall, regret, p50/p95 latency, token budget and all failure/missing-result outcomes. No AUC claim on untested data.
6. **Custody:** separately attest operator consent and evaluator/oracle custody. Same-UID write access remains a named threat; neither a hash chain nor a confidence score solves it.
7. **Independent completion:** only verified postconditions from current-world readback can support `TASK_COMPLETED`. Repeated model `finish` is abstention/verification work, never proof.

### Cherrypick verdict

**Import concepts; not the executor.** First candidate is the observation-bound action compiler and explicit refusal/handoff reason grammar. Second is versioned outer-loop experimentation, only after a credible outcome oracle and heldouts outside agent-writable roots exist. Third is optional Jev-class model support once data show that typed decision calls improve CAPT's own workload.

No CAPT RuntimeService changes, grants, provider calls, learning promotions, CI/release gates, or restarts have been performed.

## Licensing and provenance

Source inspiration: [HarnessRouter/SystemOneHarness](https://github.com/HarnessRouter/SystemOneHarness), `ab8e8f08b4a6268c0633a474423d556599ee06a4`, Apache-2.0. Prototype code was written independently for the CAPT research branch; no donor source file was copied into CAPT. If future work copies or adapts copyrighted source from this donor, retain applicable license/NOTICE information and mark changes. CAPT's original history and Knowurknot attribution remain authoritative.
