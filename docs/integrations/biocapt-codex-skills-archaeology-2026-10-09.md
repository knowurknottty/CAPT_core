# bioCAPT × CAPT — Codex skill archaeology and integration decisions (2026-10-09)

Status: **source-grounded skill review, not a claim of live cognitive execution**.
Reviewed local Codex/agent skill inventories and installed SKILL.md/reference files
read-only. No raw secrets, runtime configuration or user data were copied.

## Three different source-of-truth layers

1. **Historical instructions**: legacy `~/.codex/AGENTS.md`, `~/.agents/skills/biocapt*`, and dated June 24–29 research in their `references/` directories.
2. **Current published architecture**: CAPT Core `main` @ `af300637e89152cf501ca14d5a95736eaab8dd20`; bioCAPT Desktop `main` @ `1e107255d0a09fe4221113510ddce809ccaead41`; these are source commits, not activation receipts.
3. **Observed local live process**: bioCAPT `biocapt.live-introspection/1` sampled from PID 27452; initialized and idle, 19 HMC in-process traces, 18 ECHO store operations, QIPC nodes=0, last_cogitation=null during inspection. The process's `module_probe_kind` explicitly says object presence/initialized flag, **not active firing**. An empty cogitation receipt is **NO_VOTE**, never PROPOSED or CONVERGED.

The installed catalogue consists of a smaller Codex-specific `~/.codex/skills`
directory and a larger `~/.agents/skills` shared library. The 12 enabled
bioCAPT skills visible in UI represent instruction availability, not proof that
the associated runtime endpoints, deployments or model counts are active.

## Extracted gold — adopt mechanisms, not historical prose

| Source | Portable mechanism | Integration decision |
|---|---|---|
| `biocapt-driver` | Plan → governed dispatch → native trace → consensus → validation; explicit raw/native output preservation | Use typed CAPT cohort contract and raw evidence; **vessels are logical perspectives, not necessarily separate provider calls** |
| `biocapt-perfection` + June 24 runtime audit | Code-level root-cause mapping; watchdogs, leases, bounded async work, per-query budgets | Recheck each historic issue against current source and tests before modifying code |
| `biocapt-strength-stack` | Real IMMU false-positive tests, provider authentication backoff, memory provenance, MCP lifecycle gates | Convert each into observable admission/test contracts, not unconditional activation |
| `biocapt` degraded-module audit (June 27) | Distinguishes importable, initialized, `health_check()`, active and cogitation-completed | Formalize `HEALTHY / UNHEALTHY / UNKNOWN` per probe source; do not call import success runtime health |
| `biocapt-autonomous-training` | Detect simulated FETCH, dual counters and non-training preflight outcomes; validate checkpoints and held-out scores | Training receipt must verify actual data source, optimizer steps, checkpoint/digest, evaluation and rollback; **confidence is not ground truth** |
| `biocapt-knowledge-campus` | Epistemic tag, source attribution, quarantine and per-trace trust | Carry signed/verified lineage separately from self-reported confidence; default unverified |
| `capt-chatgpt-skills/00-capt-comm.md` + `13-core-drift-and-certification.md` | Transport secrecy, actual CAPT authority, published/live/candidate separation, serial five-pass review | Make release claims require source SHA + runtime receipt + tests + explicit capability identity |
| Current `modules/live_introspection.py` | Private Unix socket, exact GET manifest/snapshot, whitelist-only sanitized module summaries, no prompts | Reuse for **read-only observation** only; do not silently add POST/cogitation to introspection API |

## Historical hazards — reject or supersede

1. **Inconsistent module counts**: legacy skills claim 46, 82, 85, 97+, 189 or 198 modules/tools in differing eras. These are not interchangeable measurements; version them by inventory root, installed module, initialized module, healthy module, emitted module result, and exposed MCP tool.
2. **Unverified identity/provenance**: beta channel rules ask the bot to hide its model/gateway and assert hardware quantum/self-awareness as facts. Replace with truthful architecture and verified capability disclosures. Model output and quantum-inspired math do not demonstrate consciousness, independent verification or quantum hardware advantage.
3. **Training confirmation bias**: self-training skill proposes quality gates based on system confidence, optionally omits human review, and contains a documented synthetic paper-FETCH loop. Synthetic examples are *fixtures*, not research data; keep training promotion human-governed and held-out benchmarked.
4. **Unsafe operation shortcuts**: beta deployment suggests public open pairing; troubleshooting suggests global process kills and ad-hoc credential-file reads. These are not safe defaults. Preserve peer authorization, least-privilege scopes, managed process shutdown, sanitized secrets and explicit production approvals.
5. **Synthetic self-healing success rates**: FrankenCAPT self-healing skill describes bootstrapping patch-success prediction with ~200 heuristic-labelled synthetic records. Do not present trained probabilities as observed reliability. Predictor provenance must distinguish heuristic priors from real patch outcomes.
6. **Constitutional shortcut**: an older governance skill proposes skipping ETHOS for sub-100ms operations. Latency is not authority; keep pre-execution CAPT policy and lease checks on consequential operations.
7. **Stale interface assumptions**: older references use paths and methods from prior ecosystem layouts, and a troubleshooting note contains conflicting “wrong/right” constructor examples. Resolve the live implementation and run an executable contract test before proposing a migration.

## Concrete next integration contract

**Admission** — CAPT RuntimeService grants explicit narrow scope and lease to the private bioCAPT Unix socket; CAPT Node current capability does not cover the live bioCAPT directory. Never manufacture/extend grants by editing skills, configuration or bypassing the governed Node.

**Observe** — confirm actual positive authorized path using the existing real manifest/snapshot. Verify schema, time freshness, socket owner/mode, live source PID, module health and completed cogitation separately. Re-read CAPT grant state before using the result if source observation is long-running; if revoked, fail closed.

**Cogitate** — implement a **separate** opt-in native request surface with idempotency keys, bounded budgets, cancellation, exactly-once outcome reconciliation, bounded raw response summaries and verified CAPT receipts; CAPT service remains sole authorizer. No model dispatch through the read-only socket.

**Converge** — QIPC v3 keeps correlated evidence one component, preserves dissent, distinguishes measured algorithm agreement from authenticated independence; zero independent-verification claims for self-reported lineage. DeepSeek as “mouth” is a semantic rendering layer downstream of raw/native trace and never a substitute for evidence.

**Learn** — isolate KnowledgeBubble generation from training; require consent, reliable origin/provenance, dedup, contamination avoidance, actual optimizer-step and checkpoint receipts, held-out comparisons and rollback gates. Synthetic FETCH cannot be promoted into a real literature claim.

**Deploy** — run positive/negative grant tests, real same-process Unix IPC, no-unapproved-provider-call check, desktop end-to-end execution, scope and idempotency abuse tests, full CAPT suite, SHA/published/local alignment. Update skill claims *after* this evidence, not before.

## Known gate at inspection

CAPT Node capability `mcp-cap-d9e2873cd79148eb88e4` expired 2026-10-09 17:45:14 UTC. A subsequent governed node operation returned `capability_expired`, so no further local edits or execution tests were attempted. **This document does not authorize changing the capability's issuer, filesystem roots, grants, HumanApproval or billing policy.**

## Follow-up

See CAPT Core issue #175 for governed cognitive dispatch and bioCAPT Desktop issue #5 for authenticated cross-device exchange. Do not call the integration operational until an authenticated, CAPT-authorized cognitive request returns a verifiable receipt and the actual app uses that route.
