# INVENTION_ENGINE_EVIDENCE.md

- **scope**: Public invention engine (`capt_solo/engines/invention.py`), on math+physics.
- **source_commit**: `c5aa24d` (parent of this milestone commit)
- **milestone**: M4

## Supported scope (defensible)
NOT an LLM-only wrapper or generate_idea(prompt). Uses explicit structured artifacts across the 17-step workflow:

1. problem definition
2. constraints
3. existing approaches
4. functional decomposition
5. candidate principles
6. candidate mechanisms
7. candidate architectures
8. calculations (integrated directly from math/physics results)
9. physical feasibility
10. tradeoffs
11. contradictions
12. safety analysis
13. materials
14. manufacturing
15. testable hypotheses
16. prototype plan
17. validation criteria
+ failure analysis, evidence, uncertainty, revisions.

## Artifact maturity ladder (explicit, never auto-promoted by detail)
idea < hypothesis < conceptual_design < calculated_design < simulated_design
< prototype < validated_prototype < production_ready. Stage changes ONLY via
explicit `Revision` (add_revision). A highly detailed IDEA stays IDEA.

## Feasibility scoring (explainable)
`FeasibilityComponent(name, score[0..1], weight, rationale)`; overall score is the
weighted mean. Components are explainable, not a black box.

## Constraint / contradiction / safety
- Constraint tracking via `constraints` list.
- `detect_contradictions()` flags stage/data mismatches (e.g. calculated_design
  with no calculations) and explicit contradiction notes.
- `evaluate_safety()` returns PASS / REVIEW / BLOCK. BLOCK keywords: lethal,
  weapon, explosive, bioweapon, uncontained release. REVIEW when safety analysis
  is empty.

## Integration with math + physics
`add_calculation(record, label, result, source)` accepts `PhysicsResult`,
`Quantity`, or `Number` directly — no re-derivation. Results carry value,
dimension, relation, source for provenance.

## Honesty
- No patentability claims. `export_report()` explicitly states no patent search
  is performed unless wired to a source.
- Prior-art interfaces are stubs (no external patent DB call).

## Intentionally unsupported
- Automatic stage promotion from detail volume (explicit revision required).
- Patent search / legal claims.
- Autonomous physical prototyping (plan only).

## Test commands and exact results
```
python3 -m pytest tests/test_invention.py -q
# 8 passed
python3 -m pytest -q
# 572 passed (full suite)
python3 architecture/validate_registry.py
# SUMMARY: 15 checks, 0 fail, 0 warn
```

## Limitations
- Contradiction detection is structural (stage/section completeness), not semantic
  logical proof.
- Safety gate is keyword-based; not a substitute for human review of hazardous
  designs.
- Feasibility weights/scores are authored by the caller; the engine computes and
  reports them, it does not invent them.
- No simulation backend; `simulated_design` stage is a label the caller applies
  after running external simulation.

## Files changed
- `capt_solo/engines/invention.py` (new, ~250 lines)
- `tests/test_invention.py` (new, 8 tests)
