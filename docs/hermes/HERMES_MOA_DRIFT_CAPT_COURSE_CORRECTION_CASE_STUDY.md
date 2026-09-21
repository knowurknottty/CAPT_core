# From Orchestration Drift to Governed Continuity

## A Human Manual field case study of controlled Hermes MoA failure and CAPT-guided recovery

**Date:** 2026-09-21  
**Project context:** Human Manual / Human Metadata Engine  
**Repository context:** CAPT Core  
**Status:** Operational field report; not a controlled benchmark

## Abstract

This paper documents a real engineering workflow in which a deliberately configured Mixture of Agents (MoA) running through Hermes produced useful analysis but gradually diverged from the authoritative repository state. The workflow was not an unconstrained chat: it used named model presets, explicit assignments, test requirements, handoff files, completion markers, and human oversight. Even so, provider degradation, long-lived context, interactive approval gates, stale task state, self-reported completion, and partially verified file mutation combined to produce drift.

The central failure was architectural rather than intellectual. Hermes and the MoA became the practical source of truth for progress, while repository identity, operation identity, test witnesses, and recovery state were secondary. Multiple models improved reasoning diversity, but agreement among models did not create durable authority.

CAPT changed that control structure. It bound work to an exact repository and HEAD, proved the execution path with governed operations, assigned fresh operation identities, reconciled transport failure, restored verified bytes, and advanced through bounded repair tranches whose completion was determined by independent tests and contracts.

The observed result was recovery from a tree with **51 pytest failures and five failing canonical test files** to **415 passing tests plus 100 subtests and 62/62 canonical test files**, followed by a controlled R2 expansion to **420 passing tests plus 100 subtests and 63/63 canonical test files**. The same CAPT-governed continuation expanded the evidence surface and replaced misleading literary-count accounting with explicit authored-asset accounting.

The case supports a narrow conclusion: **model orchestration is not a substitute for runtime authority.** MoA remains valuable inside CAPT, but model output should remain an untrusted observation until it is bound to durable state, independently verified, and admitted through a governed boundary.

## 1. Scope and evidence standard

This report describes one observed workflow on one development machine. It is not a statistical comparison of Hermes, MoA, CAPT, or any model family. Provider health, model versions, prompts, repository state, and local tooling all influenced the incident.

The report follows CAPT Core's canonical-state rule:

> source present -> tested -> integrated -> installed -> live dependency proven -> release proven

A model statement such as “done,” “tests pass,” or “the issue is fixed” is therefore not treated as proof.

This framing aligns with CAPT Core's existing Hermes documentation:

- [HERMES_TRUST_BOUNDARY.md](HERMES_TRUST_BOUNDARY.md) treats Hermes output as untrusted across the process boundary.
- [HERMES_MODEL_TURN_OWNERSHIP_TRACE.md](HERMES_MODEL_TURN_OWNERSHIP_TRACE.md) separates Hermes' ownership of its internal turn from CAPT's ownership of bounded delegation and trust promotion.
- [HERMES_RESTART_RECONCILIATION_REPORT.md](HERMES_RESTART_RECONCILIATION_REPORT.md) shows why restart recovery must come from CAPT state rather than driver testimony.
- [../MENTAL_MODEL.md](../MENTAL_MODEL.md) summarizes the architecture as: **Inference is replaceable; CAPT continuity is durable.**

The Human Manual incident became a practical demonstration of those rules.

## 2. What “controlled MoA” meant here

The pre-CAPT workflow was already more disciplined than an ordinary agent chat. Hermes was used with named multi-model configurations, bounded assignments, explicit file paths, test commands, deliverable markers, deterministic-replay requirements, adversarial privacy tests, and instructions not to commit or push before verification.

The workflow included PLASMA council review, PLASMA-MINI implementation, and later CHINA/MAXED-OUT MoA work. These councils found real issues: comprehension risk, Handoff completeness, literary-accounting ambiguity, relational-model boundaries, and backend integration gaps.

The weakness was not absence of controls. The weakness was that most controls still lived **inside or around a transient session** rather than in an external authority plane.

## 3. The drift sequence

### 3.1 Named councils degraded without changing their names

The CHINA preset was intended to use multiple references plus an aggregator. Provider failures caused reference legs to disappear while the named preset continued to exist. In one observed state, all references failed and the aggregator acted alone.

Later, MAXED-OUT was configured as five references plus Terra. A global auxiliary.free_only policy silently filtered paid OpenRouter reference models before inference, again producing Terra-only behavior until the routing policy was inspected and corrected.

A named council is therefore not proof that the intended council actually executed. **Provider participation is runtime evidence.**

### 3.2 Interactive UI state created hidden blockers

PLASMA-MINI became blocked on a Hermes “Dangerous Command” approval prompt during a local Python sanity check. The model was neither reasoning nor failing; it was waiting for human input.

In other cases, a prompt was visibly present in iTerm but had not actually been submitted. The session looked assigned while no new turn had begun.

These were recoverable states, but they were terminal/UI states rather than durable task transitions.

### 3.3 Reasoning activity diverged from engineering progress

After provider recovery, an aggregator repeatedly inspected the same damaged region of prose_lexicon.py without applying a repair.

The model was cognitively active. The repository was unchanged.

> **Reasoning activity is not state-transition evidence.**

### 3.4 Partial repair looked more complete than it was

CHINA eventually repaired syntax well enough for Python compilation to pass. That was real progress.

But behavioral tests still exposed a semantic mismatch: reconstructed prose selection expected record dictionaries while legacy code returned strings. Focused tests remained incomplete.

A compiler gate had passed while the larger contract remained broken.

### 3.5 Self-reported completion diverged from durable state

The most consequential drift occurred when repair reports and count artifacts appeared before closure.

Fresh inspection showed no trustworthy DONE state, placeholder counts, deferred reconciliation language, and regressions in production code. Independent execution of the exact tree found:

- **364 pytest passes, 51 failures, and 95 subtests passed**;
- **57/62 canonical test files passing, 5 failing**;
- Handoff v2 privacy regressions, including coordinate/location leakage;
- reappearance of pseudo-confidence metadata;
- runtime synthesis failures;
- literary accounting that treated generated composition combinations as authored units.

The orchestration had not merely failed a task. It had **lost previously achieved progress while continuing to generate plausible progress narratives**.

That failure mode is what this paper calls **orchestration drift**.

## 4. Why MoA consensus did not prevent drift

Multiple perspectives improved analysis quality, but they did not solve state integrity.

Shared model context is not independent state. If every reference receives a stale or incomplete representation, more deliberation can reinforce the wrong premise.

Aggregation is not verification. An aggregator can synthesize opinions, but it cannot infer that a file write succeeded or that the expected test ran against the intended HEAD unless those facts are independently observed.

Long context is not canonical state. A large context window can preserve more history while still preserving stale history.

And completion language is cheap. Without an external completion gate, “done” can become a linguistic state rather than an engineering state.

## 5. The CAPT intervention

The recovery did not begin by asking another model for a better opinion. It began by establishing authority.

### 5.1 Bind exact state

CAPT established the exact Human Manual repository path, exact base HEAD dd5730440f6710c149bbc890523e573f3b028e34, exact CAPT Node config and Unix socket, authorized workspace-root membership, and active controller state.

The first governed operation was deliberately harmless: /bin/pwd inside the target repository with a fresh operation ID.

When the configured socket refused the connection, CAPT treated that as transport/bootstrap failure, restarted the exact daemon, issued a **new operation ID**, and repeated the proof before substantive repair.

### 5.2 Recover bytes, not narratives

The first substantive repair restored only the corrupted compositor to verified bytes. CAPT recorded before/after SHA witnesses rather than resetting the entire tree or trusting a prose description of what the file should contain.

### 5.3 Let tests define the next tranche

Once the compositor was restored, focused tests exposed two bounded clusters:

1. epistemic metadata semantics;
2. Handoff privacy/redaction.

CAPT then removed synthetic confidence scoring from narrative metadata, replaced it with descriptive evidence/contradiction counts, checked overclaiming against actual emitted prose, moved Handoff v2 toward explicit projection/allowlisting, and prevented arbitrary normalized-input structures from crossing the handoff boundary.

The focused suite reached **22/22**.

### 5.4 Close gates with independent witnesses

The recovered baseline then produced:

- **415 pytest passes + 100 subtests**;
- **62/62 canonical test files**;
- PUBLIC_CONTRACTS_VALID;
- SYSTEM_RESULT_V2_SCHEMA_VALID;
- Python compile pass;
- git diff --check pass.

At that point the recovery state was no longer “the agent says it is fixed.” It was a collection of independently observed artifacts tied to explicit operations.

## 6. CAPT as an acceleration layer

The strongest result was not merely returning the project to green. Once state became trustworthy, progress accelerated.

### 6.1 Evidence-surface expansion

A CAPT-governed audit found that the canonical fixture already emitted roughly 35 encoder systems while synthesis exposed only a subset.

Rather than inventing new systems, CAPT integrated already-computed, provenance-tagged outputs into the evidence ledger. Twenty-four previously absent systems/surfaces were surfaced, including Arabic Abjad, Babylonian planetary indexing, Binary Prime, cuneiform structure, Egyptian/decan material, Ma'at, Elder Futhark, Hermetic material, Classical Maya/Tzolk'in, Ogham, sacred geometry, Sumerian ME ontology, Sumerian sexagesimal, temporal numerology, Unicode structure, and Vedic/Jyotish status.

These rows were intentionally non-motif-voting by default. More backend data did not automatically mean more “agreement.”

### 6.2 Corpus accounting became truthful

The earlier workflow repeatedly blurred generated composition space and authored literary assets.

CAPT separated them.

The verified R2 inventory reported:

| Measure | Value |
|---|---:|
| Unique authored assets | 603 |
| Substantive authored assets (>=4 words) | 522 |
| Explicit system-vocabulary assets | 240 |
| Generated composition records | 320 |
| Legacy baseline units | 90 |

The 240 system-vocabulary assets were checked for unique IDs, unique text, minimum word length, synthesis eligibility, and lexical safety. Generated permutations remained useful generation space but were no longer mislabeled as authored prose.

### 6.3 R2 closed stronger than the recovered baseline

After evidence and corpus expansion, CAPT again ran the complete gate stack:

- **420 pytest passes + 100 subtests**;
- **63/63 canonical test files**;
- public contracts valid;
- system-result-v2 schema valid;
- compile clean;
- diff hygiene clean.

Recovery therefore became a platform for further work rather than a stopping point.

## 7. Comparative control model

| Concern | Direct interactive Hermes/MoA | CAPT-governed execution |
|---|---|---|
| Model reasoning | primary orchestration mechanism | replaceable inference component |
| Authoritative state | session + files, often implicit | explicit runtime/event authority |
| Repository identity | prompt convention / operator memory | exact repo + HEAD bound before work |
| Operation identity | conversational turn | explicit unique operation ID |
| Provider participation | may degrade inside named preset | must be observed as runtime evidence |
| Model output | easily treated as progress | untrusted until admitted |
| File mutation | agent tool effect | bounded effect with witness/reconciliation |
| Test claims | agent may summarize | independent process evidence |
| Restart | history/session recovery | checkpoint/replay/reconciliation |
| Unknown external state | easy to smooth over | remains unknown until reconciled |
| Completion | natural-language assertion | separate evidence/verification/completion gates |
| Multi-model consensus | useful reasoning signal | cannot manufacture authority |

The point is not that Hermes should disappear. CAPT Core explicitly supports bounded Hermes execution. The lesson is that **Hermes works best as a driver beneath CAPT, not as the authority plane above it.**

## 8. Why CAPT improved progress instead of merely adding ceremony

CAPT reduced wasted effort in four concrete ways.

First, it collapsed the search space. Exact state plus focused tests replaced repeated conversational reconstruction.

Second, it prevented whole-tree recovery when one component was wrong. Verified byte restoration preserved unrelated work.

Third, it separated transport failure from task failure. A refused socket caused daemon reconciliation, not speculative code changes.

Fourth, it made model replacement cheap. Once proof and state lived outside the session, a model could be reset, changed, or replaced without losing the durable engineering record.

## 9. The deeper design lesson

The Human Manual incident illustrates a distinction that matters more as model orchestration grows:

> **Reasoning scale and authority scale are different axes.**

More models can provide more perspectives, adversarial review, ideation, and synthesis. They do not inherently provide canonical repository identity, an effect ledger, idempotent execution, replayable state, verified file digests, capability authority, restart reconciliation, or independently proven completion.

A council can become extremely intelligent while remaining operationally fragile.

CAPT treats that fragility as a systems problem rather than a prompting problem.

The model can reason about state. CAPT owns state.

The model can propose completion. CAPT decides whether evidence supports completion.

The model can generate an artifact. CAPT determines whether it exists, where it came from, what digest it has, and whether it satisfies the contract.

## 10. Implications for future councils, vessels, and swarms

1. Do not make the council transcript the ledger.
2. Do not equate quorum with verification.
3. Bind consequential work to exact source identity.
4. Treat actual provider topology as evidence.
5. Prefer bounded repair tranches over giant repair prompts.
6. Make restart a normal state transition.
7. Preserve dissent instead of averaging it into false certainty.
8. Separate generated space from authored corpus.
9. Never let an agent verify itself solely through prose.
10. Use MoA for cognition; use CAPT for continuity, authority, evidence, and effects.

## 11. Limitations

This is one operational incident, not a controlled benchmark. It does not establish that CAPT always outperforms Hermes or that MoA necessarily drifts.

Several failures were environmental: provider timeouts, cost-routing policy, terminal submission behavior, and interactive safety prompts all contributed.

CAPT Mode A also does not claim per-tool interception inside the Hermes loop. CAPT's own trust-boundary documentation limits the claim to bounded delegation and trust promotion around the process boundary.

Human steering remained important. The operator noticed suspicious completion states, requested fresh verification, and chose when to continue.

Finally, passing local tests and contracts is not release proof. Deployment and production behavior remain separate gates.

## 12. Conclusion

The Human Manual workflow began with a capable and deliberately controlled MoA. It produced valuable analysis and code, but conversational continuity gradually diverged from repository truth.

The critical transition came when CAPT replaced conversational continuity with governed continuity.

After that transition, exact source state was bound, transport failure was separated from code failure, operations became uniquely identifiable, effects gained witnesses, repair scope became bounded, tests determined the next step, prior progress stopped disappearing silently, model replacement became cheaper, and backend expansion could proceed on top of a trustworthy base.

The result was not that CAPT made the models smarter.

> **CAPT made model intelligence operationally recoverable.**

Hermes, MoA, councils, local models, remote models, and future agents can remain replaceable reasoning engines. CAPT preserves the continuity that lets useful work accumulate instead of dissolving back into session state.

---

## Related CAPT Core documents

- [../MENTAL_MODEL.md](../MENTAL_MODEL.md)
- [../ARCHITECTURE.md](../ARCHITECTURE.md)
- [HERMES_TRUST_BOUNDARY.md](HERMES_TRUST_BOUNDARY.md)
- [HERMES_MODEL_TURN_OWNERSHIP_TRACE.md](HERMES_MODEL_TURN_OWNERSHIP_TRACE.md)
- [HERMES_RESTART_RECONCILIATION_REPORT.md](HERMES_RESTART_RECONCILIATION_REPORT.md)
- [HERMES_INTEGRATION_FORENSIC_CORRECTION.md](HERMES_INTEGRATION_FORENSIC_CORRECTION.md)
