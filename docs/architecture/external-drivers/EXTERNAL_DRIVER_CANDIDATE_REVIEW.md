# External Driver Candidate Review — Gate A

Date: 2026-08-03
Author: HY3 engineering agent (CAPT-governed)
Purpose: evaluate candidates for the Gate A External ExecutionDriver conformance proof.

## Selection order and result

| # | Candidate | Repo | License | Lang | Py req | Installable here? | Selected? |
|---|-----------|------|---------|------|--------|-------------------|-----------|
| 1 | OpenHarness | HKUDS/OpenHarness | MIT | Python | >=3.10 | YES (isolated venv py3.12) | **YES** |
| 2 | DeepAgents | langchain-ai/deepagents | MIT | Python | >=3.11 | NO (system py3.9.6; no 3.11 in default PATH) | No |
| 3 | OpenAI Agents SDK | openai/openai-agents-python | MIT | Python | >=3.10 | NO (system py3.9.6) | No |

## OpenHarness (selected)

- Canonical repo: https://github.com/HKUDS/OpenHarness
- Package: `openharness-ai==0.1.9` (PyPI), MIT
- Architecture: 10-subsystem agent harness (tools, skills, memory, multi-agent
  coordination). CLI binary `oh`; non-interactive print mode `oh -p`.
- Local execution: confirmed. Uses OpenAI-compatible client; `api_format` must be
  forced to `openai` and `base_url` pointed at a local Ollama endpoint
  (`http://127.0.0.1:11434/v1`). With a local Ollama model (`ornith-1.0-9b`),
  the harness executes real analysis with NO hosted provider.
- Tool surface: includes read/write/shell/web tools, but in `--permission-mode
  default` + non-interactive `--print`, write/shell tools are denied (no approval
  possible), enforcing read-only for the bounded task. Verified: target repo
  digest unchanged after execution.
- Security: runs as a separate subprocess with an allowlisted environment that
  STRIPS all hosted credentials (Anthropic/OpenAI/GitHub/cloud keys, SSH agent).
  Only localhost Ollama network contact observed.
- Reversal conditions: if OpenHarness could not be installed/executed safely or
  reproducibly (e.g. required a hosted key, or could not be sandboxed), we would
  fall through to DeepAgents, then OpenAI Agents SDK. Neither was needed.

## DeepAgents (rejected)

- Requires Python >=3.11. The environment's default Python is 3.9.6; a 3.11
  interpreter exists at `~/.local/bin/python3.11` but the simplest reproducible
  path was OpenHarness in an isolated venv. DeepAgents also bundles filesystem
  write/shell by default, increasing sandbox burden. Not needed because
  OpenHarness satisfied the requirements first.

## OpenAI Agents SDK (rejected / not reached)

- Requires Python >=3.10. Not evaluated in depth because OpenHarness (candidate 1)
  was selected and executed successfully. Recorded as the fallback only.

## License analysis

All three candidates are MIT. OpenHarness MIT is compatible with CAPT's
permissive integration (adapter shells out; no copy of upstream code into CAPT).
No license conflict.

## Compatibility analysis

OpenHarness 0.1.9 requires Python >=3.10; satisfied via isolated venv (py3.12).
Ollama OpenAI-compatible endpoint is stable. No ABI concerns (subprocess boundary).

## Security implications

- External harness runs in a separate process with minimized env (no secrets).
- Only localhost Ollama contacted; no egress to hosted providers.
- CAPT retains all authority: the harness returns only untrusted observations;
  CAPT validates, verifies, and promotes to evidence/claims.
- Residual: `verify_lease` does not enforce max-use exhaustion (frozen M0-B gap,
  recorded separately). Hosted keys are stripped, but the harness binary itself
  is third-party code; it is run with least authority.

## Reversal conditions

If a future environment lacks local Ollama or cannot install OpenHarness 0.1.9
reproducibly, re-run candidate forensics and select DeepAgents/OpenAI SDK per the
same rules. The adapter is isolated; swapping the external harness does not change
CAPT contracts.
