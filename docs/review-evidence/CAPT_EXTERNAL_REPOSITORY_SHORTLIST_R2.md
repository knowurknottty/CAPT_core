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

## Intake batch B — 16 additional repositories (2026-10-12)

All candidates below have verified repository identities and pinned branch HEADs, **but have not passed RRDS-1 full-source inspection or permission-to-copy verification**. Classifications are preliminary. Each line belongs to the same machine-readable R2 cohort review queue; duplicates in the user's links were removed.

| Repository / pinned HEAD | CAPT surface | Initial routing | Specific mechanisms to inspect |
|---|---|---|---|
| [github/spec-kit](https://github.com/github/spec-kit) `6c62e10d` | CAPT Core / project router | **CHERRY_PICK_CANDIDATE** | Specification-driven requirements→plans→tasks and evidence gates |
| [garrytan/gstack](https://github.com/garrytan/gstack) `dbf400ec` | CAPT vessels / CAPT Bot | **CHERRY_PICK_CANDIDATE** | Role-specialized engineering, design, release and review skills |
| [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents) `f99f6aa9` | CAPT vessels / CAPT Bot | **VESSEL_AND_CAPTBOT_TEMPLATE_CANDIDATE** | Turn agent/persona templates into scoped analytical charters or governed bot roles; never independent authority |
| [lsdefine/GenericAgent](https://github.com/lsdefine/GenericAgent) `6e0c54f6` | Ouroboros / skill foundry | **REIMPLEMENT_SEMANTICS** | Self-evolving skill structures and token-efficient learning without unbounded agent control |
| [zilliztech/claude-context](https://github.com/zilliztech/claude-context) `6fc318b4` | CAPTMem / ContextPack | **CHERRY_PICK_CANDIDATE** | Code search and semantic-retrieval MCP mechanisms; respect secrecy and provenance |
| [modimihir07/agentic-os](https://github.com/modimihir07/agentic-os) `c7ebbb41` | CAPT cohorts / Hermes / Bot | **CHERRY_PICK_CANDIDATE** | Agent scheduling, skills hub and provider cost analytics; governed dispatch only |
| [Imbad0202/academic-research-skills](https://github.com/Imbad0202/academic-research-skills) `d1e51716` | CAPTResearch / CAPTSciLab | **DESIGN_REFERENCE_ONLY_PENDING_LICENSE** | Research, drafting and verification skill patterns; GitHub license reports NOASSERTION |
| [t8y2/dbx](https://github.com/t8y2/dbx) `9f6e9af6` | database adapters / TUI | **DESIGN_REFERENCE_ONLY** | Database client/query UX; no direct database access bypassing broker |
| [phuryn/pm-skills](https://github.com/phuryn/pm-skills) `c68487d7` | project router / vessels / Bot | **CHERRY_PICK_CANDIDATE** | Product discovery, planning and launch skill templates |
| [apple/container](https://github.com/apple/container) `aa8b8307` | CAPTsec / macOS execution boundary | **EXTERNAL_SERVICE_BOUNDARY** | Apple Silicon VM-backed container isolation; inspect mounts, networking, privilege and operational semantics |
| [modelcontextprotocol/ext-apps](https://github.com/modelcontextprotocol/ext-apps) `82221c0c` | CAPT MCP / desktop UI | **DESIGN_REFERENCE_ONLY_PENDING_LICENSE** | MCP Apps protocol and SDK for embedded UI; GitHub license reports NOASSERTION |
| [yogesh-tessl/Security-Claw](https://github.com/yogesh-tessl/Security-Claw) `ff021dc3` | CAPTsec RedTeam | **REDTEAM_ONLY** | Adversarial threat and harness design; no autonomous offensive deployment |
| [CronusL-1141/AI-company](https://github.com/CronusL-1141/AI-company) `01ae582d` | CAPT Bot / vessels | **VESSEL_AND_CAPTBOT_TEMPLATE_CANDIDATE** | Agent roles, orchestration hooks and pipeline structures recast into bounded vessels and bots |
| [23blocks-OS/ai-maestro](https://github.com/23blocks-OS/ai-maestro) `0d074504` | cohorts / CAPTMem / Core | **CHERRY_PICK_CANDIDATE** | Agent skills, code-graph search, memory and cross-agent handoff patterns |
| [locaith/bio-memory-ai-locaith](https://github.com/locaith/bio-memory-ai-locaith) `91868253` | bioCAPT / CAPTMem | **CHERRY_PICK_CANDIDATE** | Bio-inspired memory and context-retention design; require falsifiable improvement evidence |
| [farion1231/cc-switch](https://github.com/farion1231/cc-switch) `90fb37ff` | CAPT macOS / provider management | **CHERRY_PICK_CANDIDATE** | Provider switching and configuration UX, never credential duplication or weakened authority |

**Cohort contract:** independent DeepSeek 4.1, MiMo 2.6, and GLM 5.3 Flash review perspectives (22 logical vessels each), same pinned R2 input, one governed cohort dispatch per model unless otherwise authorized. For each donor, demand a verifiable full-tree RRDS-1 source census, pinned license text, exact functions/paths worth transplanting, tests, safety gates, and one final **CHERRY_PICK / REIMPLEMENT / DESIGN_ONLY / REDTEAM / REJECT** disposition. No automatic code transplant, model execution, or HumanApproval is performed by adding this queue.

**Important:** the old six-file CAPT-UPG DeepSeek review remains frozen and unmodified; this is a new, separately approved repository-review intake. GitHub's `NOASSERTION` is a license classification, not evidence that reuse is permitted; verify each pinned license before any copy.
