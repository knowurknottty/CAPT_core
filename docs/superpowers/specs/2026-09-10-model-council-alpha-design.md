# CAPT Model Council Alpha Design

Status: `OWNER_APPROVED_ALPHA`
Date: 2026-09-10
Supersedes: August 19 Council hard-limit and scheduling assumptions where they conflict.

## Mission

Make multi-model deliberation a governed CAPT primitive rather than a parallel-chat feature. A Council coordinates Cohorts; each Cohort is one provider/model cognitive source; Vessels are parallel bounded perspectives that inherit that Cohort identity.

The alpha must preserve raw minority findings, evidence lineage, contradiction structure, model-family diversity, and transport timing. A final language synthesizer is never epistemic authority and may not invent a claim absent from Council state.

## Tier contract

| Tier | Cohorts | Vessels per Cohort | Logical initial blast |
| --- | ---: | ---: | ---: |
| small | 2 | 3 | 6 |
| medium | 4 | 6 | 24 |
| large | 12 | 9 | 108 |
| extreme | 24 | 18-1000 | 432-24000 |

`MAX_DISTINCT_COHORTS = 24` and `MAX_VESSELS_PER_COHORT = 1000`. Extreme defaults to 18 Vessels per Cohort and always requires explicit launch acknowledgement.
## Dispatch semantics

Council planning creates the complete logical vessel set before any transport admission. CAPT must not serialize by model/cohort lane.

Transport/provider backpressure is a lower-level resource concern. Each Vessel tracks distinct timestamps for logical dispatch, transport admission, provider start, and completion so provider throttling cannot be mistaken for CAPT orchestration.

The immutable Council digest binds tier, Cohort provider/model identity, vessel cardinality, directives, synthesis policy, and challenge policy. Any mutation after approval requires a new digest and approval.

## Epistemic state

Council outputs are structured as ClaimObservations before synthesis. Each observation retains Cohort, Vessel, stance, confidence, evidence IDs, assumptions, and optional uncertainty reason.

The deterministic Council analysis layer derives:
- support and dissent sets by Cohort and Vessel;
- consensus/minority/disputed/insufficient-evidence status;
- contradiction edges;
- diversity counts based on distinct provider/model Cohorts, never raw Vessel count;
- challenge candidates for material disputes, weak consensus, unsupported unanimity, or high-confidence minorities.

Majority is not verification. Verification and ClaimGuard remain separate CAPT authority paths.
## Governance and cost safety

A launch preview must expose logical call count, Cohort/model composition, local/cloud classification when known, token envelope when supplied, estimated provider cost when pricing metadata is supplied, and challenge reserve.

Extreme requires an explicit acknowledgement token bound to the Council digest. Requests above the default 432-Vessel Extreme topology additionally require an explicit custom-scale acknowledgement. Cloud execution may be rejected by policy when no maximum spend is supplied; the Council planner itself never fabricates pricing.

No Council component grants tool, filesystem, network, provider, or approval authority. Child execution scope inherits and may narrow approved parent scope; it never widens it.

## Alpha component boundary

`capt_runtime/council.py` owns immutable definitions, tier presets, canonical digesting, logical blast expansion, timing state, claim analysis, challenge selection, and launch interlock decisions.

`capt_runtime/aggregates/council_state.py` owns durable Council session state. `GovernedRuntimeService` owns Council plan admission and state transitions. `capt_ui/operator/council_chamber.py` is a read-only projection over authoritative state.

The alpha does not create a second runtime and does not directly call providers. Existing governed DriverRun/provider execution remains the only external model-effect path.

## Alpha proof gates

Required tests cover 6, 24, 108, 432, and 24,000 logical Vessels; exact Cohort-to-model inheritance; digest mutation; Extreme interlocks; full logical blast ordering; transport timestamp separation; dissent preservation; majority-not-verification; challenge selection; aggregate replay/idempotency; and operator projection.

The 24,000-Vessel proof is structural and must not perform 24,000 paid provider calls.