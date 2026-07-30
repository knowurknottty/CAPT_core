# CONCEPT_EVOLUTION — Lineage of CAPT Ideas

Status: RECOVERED (knowledge archaeology pass, 2026-07-30)
Purpose: show how each major concept originated, evolved, was renamed, absorbed,
or became obsolete. Documents lineage rather than treating concepts as unrelated.

## Proof Engine → Foundry Proof
- Origin: PROOF_ENGINE.md described a standalone Proof Engine.
- Evolution: implemented inside `capt_solo/foundry/prove.py` + `proof.py` as the
  Foundry subsystem. The name "Proof Engine" survived as the conceptual label;
  the code lives under Foundry.
- Lineage: PROOF_ENGINE.md (concept) → capt_solo.foundry.proof (code). ABSORBED.
- Duplicate risk: none (single implementation).

## Evidence Engine ↔ VSI
- Origin: separate docs (EVIDENCE_MODEL.md, VSI_MODEL.md).
- Evolution: Evidence answers "why is the proof justified"; VSI answers "what
  state was proven". They were integrated in `5e51203` (VSI<->Evidence integration).
- Lineage: two concepts, one subsystem pair (capt_solo.evidence + capt_solo.verification).
- Duplicate risk: none — deliberately kept distinct (ADR-0011 terminology).

## Anti-Token-Extraction — two implementations
- Origin: `memory/antitoken.py` (v0.4, deterministic, stateless) AND
  `components/anti_token_extraction.py` (ATE branch, MCP-based).
- Evolution: the memory/ version shipped in baseline; the components/ version is
  the cherry-pick candidate with upstream MCP integration.
- Lineage: parallel implementations, NOT duplicates — memory/ is the core
  reduction; components/ is the external-MCP adapter. Recommend keeping both:
  memory/ for local, components/ for MCP interop.
- Conflict: components/ version removes `_ate_stdio_server.py` (local child) in
  favor of real upstream MCP. The stdio server does not exist in baseline, so the
  removal is a no-op there.

## ClaimGuard ↔ Proof Engine ↔ Governance
- Origin: three separate v0.4 concept docs.
- Evolution: ClaimGuard (claim scanning) sits ON TOP of Proof Engine (evidence
  aggregation) and Governance (audited action). They are complementary layers,
  not duplicates. None implemented except the Proof Engine substrate.
- Lineage: three concepts, one shipped substrate (Proof/Foundry), two conceptual
  wrappers.

## Knowledge Bubbles ↔ Export/Import ↔ CTP
- Origin: Knowledge Bubbles (portability), Export/Import (memory), CTP (transactions).
- Evolution: Bubbles depend on CTP for governed install and on Export/Import for
  artifact serialization. The CTP + Export substrate shipped; the Bubble wrapper
  is the missing integration. NOT duplicates — Bubble is the orchestration.

## Reasoning Core sub-lobes (CIG/HDR/META/CONSC/QIPC/RYS/NEDA)
- Origin: registry "missing"; forensic CANONICAL_MODULE_REGISTRY from biocapt-ecosystem.
- Evolution: these are EXTERNAL concepts ported from the broader bioCAPT
  ecosystem, not invented in capt-solo. They appear in the registry as
  forward-looking capabilities. Status: research / PORT-or-exclude.
- Lineage: biocapt-ecosystem → capt-solo registry (aspirational). NOT implemented.

## CAPTLANG
- Origin: Biocapt-ecosystem-fullcaptlang (authoritative source per memory note).
- Evolution: a separate compiled language; not part of capt-solo runtime. Listed
  in registry as external package.
- Lineage: external → registry reference. NOT a capt-solo concept.

## Release Identity: self-SHA → Option A
- Origin: original v0.5 freeze attempted `candidate_sha == HEAD` (impossible).
- Evolution: SHA-loop incident (2026-07-30) proved the invariant unsatisfiable.
  Owner approved Option A: source commit + metadata commit; candidate_sha names
  the source ancestor. Validator detects context (source vs metadata).
- Lineage: defective invariant → Option A (mathematically valid). DOCUMENTED in
  CANDIDATE_FREEZE_PROTOCOL.md. This is the clearest example of a concept that
  evolved because the original was mathematically impossible.

## Six-Pillar vs Internal Layers
- Origin: internal layer model (CAPT_CANON L3–L11) vs public six-pillar (ADR-0008).
- Evolution: the six-pillar model is a PROJECTION of the internal layers for the
  public boundary; it does not replace them (ARCHITECTURE.md clarifies).
- Lineage: internal layers (spec) → six-pillar (public view). COMPLEMENTARY.

## Ontology → everything
- Origin: ADR-0002 (ontology precedes knowledge/memory/trust/governance).
- Evolution: the `ontology` subsystem (1 py, no dedicated test) is the seed; the
  schema files in `architecture/*.schema.json` are the operational ontology.
- Lineage: principle (ADR-0002) → schema files (implemented) + ontology module
  (partial). FLAGGED: ontology module needs a test or explicit internal mark.

## Obsolete / superseded (documented, not discarded)
- `_ate_stdio_server.py` (local child adapter): superseded by real upstream MCP
  in the ATE branch. Removed there; absent in baseline. OBSOLETE by design.
- v0.4.0/v0.4.1 public contracts: preserved by CAPT_CANON compatibility rule;
  not obsolete, but superseded by v0.5 freeze protocol for release identity.
- Forensic reconstruction corpus recommendations: explicitly NOT adopted as
  authority (FULL_ARCHITECTURE_IMPLEMENTATION_MATRIX.md). Treated as evidence,
  not command.

## Conceptual duplicates (resolved)
- "Proof Engine" vs "Foundry Proof" — same thing, naming only.
- "Memory Compression (AntiToken)" vs "AntiToken extraction" — same (registry
  lists both names; one implementation in memory/antitoken.py).
- "CSG" path confusion: registry says `csg` (missing) but implementation is
  `memory/csg.py` (complete). RESOLVED: CSG is shipped, just not at the path the
  registry's capability name implies. Update registry path reference.
