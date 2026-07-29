# CAPT Core v0.5.0

> AI work is easy to generate and hard to verify.

CAPT is a local-first verification substrate for AI systems. It binds claims,
context, tool results, and actions to evidence, state, policy, and receipts so
they can be inspected, reproduced, invalidated, and recovered across models and
runtimes.

CAPT is pre-release software. It has not been published to a package registry,
tagged as v0.5.0, or approved for public release. See `RELEASE_STATE.md` for the
current gate status.

## What CAPT Does

- records evidence with provenance, scope, confidence, and invalidation;
- binds verification to concrete repository and runtime state through Verified
  State Identity (VSI);
- builds deterministic ContextPack v1 artifacts with explicit assumptions and
  protected-fact validation;
- records consequential local operations through append-only CTP receipts;
- preserves local memory, recovery, export, and migration behavior;
- exposes explicit governance, capability, proof, and failure boundaries;
- runs underneath models and protocols rather than requiring one provider.

## What CAPT Does Not Do

CAPT does not train foundation models, replace model providers, replace MCP or
A2A, require cloud state, expose hidden model reasoning, turn every claim into
fact, remove uncertainty, or guarantee legal, scientific, or security
correctness by branding alone.

## Five-Minute Verification Flow

From an obtained source checkout:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
capt --json doctor
python examples/verification_first/run.py --output /tmp/capt-verification-demo
```

The example creates a local subject, captures state-bound verification evidence,
produces a CTP receipt and deterministic ContextPack, changes the subject, and
shows that the earlier verification no longer applies. It performs no network
activity.

Detailed walkthrough:
`docs/tutorials/VERIFY_AI_WORK_IN_FIVE_MINUTES.md`.

## Adopt Only What You Need

| Profile | Import | Persistence | Network | Stability |
|---|---|---|---|---|
| Evidence | `capt_solo.evidence` | none by default | none | Provisional |
| Verification | `capt_solo.verification` | optional local JSONL | none | Provisional |
| Context | `capt_solo.contextpack` | none | none | Stable ContextPack v1 |
| Transaction | `capt_solo.ctp` | explicit local JSONL | none | Stable |
| Workspace | `capt_solo.workspace` | explicit workspace files | none | Provisional |
| Full runtime | `capt_solo.api` | local SQLite and JSONL | none by default | Stable facade |

The complete compatibility declaration is in
`docs/PUBLIC_API_STABILITY.md`.

## Public Architecture

CAPT's public model has six pillars:

1. Identity & Scope
2. Evidence
3. Verification
4. Context
5. Transactions
6. Governance

Memory, Workspace, Knowledge, Foundry, KHSB, Lifecycle, and domain engines are
services or adapters over those pillars. The constitutional L0-L11 model and
subsystem registry remain the internal ownership and research catalogue.

See `docs/PUBLIC_ARCHITECTURE.md`.

## Local-First Boundary

- No required cloud account, external database, or Docker runtime.
- Core imports perform no network activity.
- PULSE is an experimental optional gateway, disabled by default, and imports
  its network library only after explicit configuration and use.
- SQLite and inspectable local files are the default stores.
- `CAPT_SOLO_HOME` controls runtime persistence.
- Export, deletion, and exit do not require a service account.

“Local-first” means no network requirement or hidden egress. It does not mean
the optional PULSE module is incapable of an explicitly authorized network call.

## Verification Commands

Run these commands against the checkout you are evaluating:

```bash
python3 -m pytest -q
python3 verify_runtime.py
python3 -m compileall -q capt_solo capt_cli.py tools
python3 capt_cli.py architecture validate
python3 capt_cli.py workspace validate
python3 capt_cli.py release validate
python3 -m build
```

Do not copy test totals or artifact hashes between commits. Exact final-candidate
evidence belongs in `docs/release/RELEASE_VERIFICATION_V0.5.md`.

## Installed CLI

Installing the distribution provides `capt`:

```bash
capt --help
capt --json doctor
capt verify status
capt evidence status
```

Repository-only commands such as architecture and workspace validation require a
source checkout containing the governed files they inspect.

## Research Heritage

CAPT grew from a biologically inspired cognitive architecture. HMC, ENGRAM,
DREAM, cognitive modules, and domain engines remain documented and testable
where implemented. They do not define the public verification kernel and their
research maturity is stated separately from stable API status.

The internal catalogue lives in `architecture/registry.yaml` and
`docs/CANONICAL_ARCHITECTURE.md`.

## Security and Release Status

- Security policy and trust boundaries: `SECURITY_BOUNDARIES.md`
- Public/private boundary: `docs/RELEASE_GOVERNANCE.md`
- Current release decision: `RELEASE_STATE.md`
- Bounded release security report:
  `docs/security/RELEASE_SECURITY_REPORT_V0.5.md`

No tag, publication, upload, deployment, or merge is authorized by a passing
local verification run.

## License

MIT. See `LICENSE`.
