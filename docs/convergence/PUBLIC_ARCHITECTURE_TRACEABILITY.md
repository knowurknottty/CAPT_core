# PUBLIC_ARCHITECTURE_TRACEABILITY — every architectural claim mapped

Generated: 2026-07-30. Scope: CURRENT public artifacts only (integration README,
PUBLIC_ARCHITECTURE.md, API manifest, CLI, whitepaper-on-main, package metadata).
We ask per claim: Implemented? Verified? Tested? Documented accurately? Requires
Spaces? Requires adapters?

## Claims (from integration README + PUBLIC_ARCHITECTURE.md + API manifest)

| # | Architectural statement | Impl | Verified | Tested | Doc-accurate | Needs Spaces | Needs Adapters |
|---|---|---|---|---|---|---|---|
| A1 | Local-first verification substrate | ✅ | ✅ | ✅ | ✅ | no | no |
| A2 | Model-agnostic / no harness dependency | ✅ | ✅ (zero hermes imports; socket-deny import) | ✅ (import tests) | ✅ (architecture-level claim) | no | no (architecture-level only) |
| A3 | Persistent memory with namespaces, tags, provenance, confidence, export/import, backup | ✅ | ✅ | ✅ | ✅ | no | no |
| A4 | CTP append-only journals, receipts, idempotency, audit, recovery | ✅ | ✅ | ✅ | ✅ | no | no |
| A5 | KHSB pub/sub + req/reply with timeout/ack | ✅ | ✅ | ✅ | ✅ | no | no |
| A6 | Skill Foundry 12-stage harness + lifecycle states | ✅ | ✅ | ✅ | ✅ | no | no |
| A7 | Proof Engine: evidence + requirement aggregation; capability not "verified" without proof | ✅ | ✅ | ✅ | ✅ | no | no |
| A8 | Capability Registry explicit states (candidate/validated/proven/verified/degraded/deprecated/revoked/experimental) | ✅ | ✅ | ✅ | ✅ | no | no |
| A9 | ClaimGuard prevents unsupported completion claims | ✅ | ✅ | ✅ | ✅ | no | no |
| A10 | Deterministic ContextPack v1 with assumptions + protected-fact validation | ✅ | ✅ | ✅ | ✅ | no | no |
| A11 | VSI binds verification to repository/runtime state | ✅ | ✅ | ✅ | ✅ | no | no |
| A12 | Governance, capability, proof, failure boundaries explicit | ✅ | ✅ | ✅ | ✅ | no | no |
| A13 | Runs underneath models/protocols, not requiring one provider | ✅ | ✅ | ✅ | ✅ | no | no |
| A14 | "Adapters: CLI · CI · IDE · MCP · A2A · Hermes · model/tool providers" (architecture diagram) | 🟡 | 🟡 | 🟡 | ⚠️ | no | partial |
| A15 | "A future adapter may translate CAPT to MCP/A2A" (architecture doc L104) | 🔮 future | n/a | n/a | ✅ (explicitly future) | no | yes (future, not claimed present) |
| A16 | "semantic and vector search adapters" (whitepaper L498) | 🟡 | partial | partial | ⚠️ (seam claimed, not full adapter) | no | partial |
| A17 | "namespaced extension points that reduce future migration cost" (architecture doc L109) | ✅ | ✅ | ✅ | ✅ | no | no |

## Notes on A14/A16 (the only adapter-adjacent claims)
- A14 lists adapters as an architecture LAYER (CLI/CI/IDE/MCP/A2A/Hermes/
  providers). These are integration surfaces, not a runtime-generation contract.
  CLI/CI/Hermes plugin exist; MCP/A2A are noted as external protocols (L104).
  The claim is accurate AS AN ARCHITECTURE LAYER, not as "operational model
  adapters shipped."
- A16 "semantic and vector search adapters" — the memory engine has a
  "semantic-search adapter seam" (whitepaper L136); this is a SEAM, not a
  delivered adapter. The whitepaper frames it as current capability language;
  strictly it is a reserved seam. This is a minor documentation-truth item
  (claim ledger: keep "seam", not "adapter").

## Conclusion for Q4
Every CURRENT public architectural claim is satisfied WITHOUT Spaces and WITHOUT
an operational runtime-adapter contract. The only adapter language is either
(a) architecture-layer integration surfaces (accurate), or (b) explicitly-future
(A15) or seam-level (A16) language that should be tightened but is not a false
present-tense claim of a shipped adapter. No claim requires Spaces. No claim
requires the doc-15 §E operational adapter contract to be TRUE today.
