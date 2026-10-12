# CAPT external repository shortlist — R2 intake addendum

**Status:** proposed for review; not yet inspected under RRDS-1, verified, integrated, or certified.

This note is the human-readable **CAPT cherry-pick/integration shortlist** accompanying [`CAPT_EXTERNAL_DONOR_COHORT_QUEUE_R2.json`](CAPT_EXTERNAL_DONOR_COHORT_QUEUE_R2.json). It is an **append-only intake** rather than a replacement for the 2026-09-24 historical 40-donor OpenWorker/openJiuwen mission or the separately frozen CAPT-UPG-025..074 six-source DeepSeek/MiMo/GLM council input.

## Cherry-pick or semantic reimplementation — pending verification

| Repository | Pin (observed 2026-10-12) | Proposed CAPT substrate | Status |
|---|---|---|---|
| [RenyunLi0116/agent-memory-galaxy](https://github.com/RenyunLi0116/agent-memory-galaxy) | `17b5279189e4c97462a9f59324593802e0e61e9f` | CAPTMem / cross-machine ContextPack provenance / governed agent presence and memory relay | **QUEUED_NOT_REVIEWED** |

### Candidate mechanisms

- **Memory provenance:** scan reviewed `agent_memory.md`, normalize minimally necessary session metadata, and map source ↔ tool/agent/user/machine ↔ derived memory. Reuse CAPT's existing EventStore and authenticated identity instead of importing a competing authoritative graph store.
- **Presence and handoff:** evaluate `auto_presence.py`, `relay.py` and `sync_watch.sh` for bounded, explicit, receipt-backed cross-machine synchronizations. Treat `SYNC_INBOX.md` as *untrusted data*, never automatic authority.
- **Viewer:** inspect the static graph visualization as a user interface for read-only, provenance-filtered CAPT memory/ContextPacks, not an authorization mechanism.
- **Privacy:** examine `encrypt.py`, plaintext hub artifacts and GitHub Pages exposure. Require private-by-default storage and a credential/redaction audit before enabling distribution.

### Red-team scrutiny

Test malicious memory entries and injected inbox instructions, agent/user attribution spoofing, background synchronization without authorization, secret leakage, plaintext Pages publishing, same-UID process scope escalation, and loss of provenance on graph merges.

**Licensing gate:** GitHub returned `license: null`, and the observed root listing did not contain a `LICENSE` file. Treat copying or redistributing upstream code as **blocked until licensing is resolved**. Independently authored compatible semantics and architectural comparison may still be evaluated. Do not infer a license from the repository's public visibility.

### Cohort handoff

Include this entry in the **next donor-repository review batch** shared with three *independent* DeepSeek 4.1 Flash, MiMo 2.6 Flash and GLM 5.3 Flash cohorts, each with 22 logical vessel perspectives. Cohorts do not run in parallel by default. Never reinterpret the 22 perspectives as 22 model HTTP calls. Each review must cite a pinned upstream SHA and produce full-tree RRDS-1 census/inspection receipts, clear `CHERRY_PICK_CANDIDATE / REIMPLEMENT_SEMANTICS / DESIGN_REFERENCE_ONLY / REDTEAM_ONLY / REJECT` disposition, and adversarial regression proposals. **No completed source review is asserted here.**

This addition **does not change** the SHA-256 of any previously approved council input or retroactively alter earlier approvals or reviews.
