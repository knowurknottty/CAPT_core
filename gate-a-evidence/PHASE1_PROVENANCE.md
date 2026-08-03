# Gate A — Phase 1 Provenance & Environment Evidence

Date: 2026-08-03 (UTC)
Recorded by: HY3 engineering agent (CAPT-governed)

## Repository / worktree
- Repository: knowurknottty/CAPT_core
- Worktree: /Users/knowurknot/capt-m0a-gatea
- Branch: feat/capt-runtime-external-driver-conformance
- HEAD: 5fb323d6edd8511b687eaec9f6656fc4b4d0b320 (frozen M0 integrated main)
- Worktree status: clean except untracked `.venv-external/` and `external_driver_requirements.lock` (intentionally isolated, gitignored below)
- capt-runtime-m0 tag target: 5fb323d6edd8511b687eaec9f6656fc4b4d0b320

## Isolated environment
- Isolated venv: /Users/knowurknot/capt-m0a-gatea/.venv-external
- Venv Python: 3.12.13 (Homebrew /opt/homebrew/bin/python3.12)
- System Python (unchanged): 3.9.6
- No global installation; dependency confined to the venv.

## OpenHarness package
- Package name: openharness-ai
- Exact version: 0.1.9
- Source repository: https://github.com/HKUDS/OpenHarness (MIT)
- License: MIT (License-Expression: MIT)
- Python requirement: >=3.10
- Installed location: .venv-external/lib/python3.12/site-packages/openharness
- Console scripts: oh, ohmo, openh
- Wheel RECORD hashes (from openharness_ai-0.1.9.dist-info/RECORD):
  - bin/oh  sha256=MPcHSj3WvJlpohON3zcgGf1yx043lRnI0_idgs95PpM
  - bin/ohmo sha256=Gr2S7l21_FFVU2ObugycePszSipFHmN65CIPU5mmQaM
  - bin/openh sha256=MPcHSj3WvJlpohON3zcgGf1yx043lRnI0_idgs95PpM
- Installed package tree fingerprint (sha256 over openharness/ source files):
  dcad32167e95717113009f58bd9c2271 (prefix; full hash in audit log)
- Dependency lock: external_driver_requirements.lock (pip freeze, 77 packages)

## Local model provider (Ollama)
- Endpoint: http://127.0.0.1:11434 (OpenAI-compatible /v1)
- Status: reachable (OLLAMA_OK)
- Available local models:
  - ornith-1.0-9b:latest (5.63 GB) — LOCAL, selected for Gate A
  - minimax-m2.5:cloud (remote/cloud, not used)
  - minimax-m2.7:cloud (remote/cloud, not used)
  - gpt-oss:120b-cloud (remote/cloud, not used)
- Selected model: ornith-1.0-9b (fully local, no hosted provider)

## Credentials / environment
- No hosted-provider API keys are used for OpenHarness execution.
- OPENHARNESS_API_KEY is set to a non-secret local placeholder ("ollama-local").
- Hosted LLM keys present in the AGENT's own environment (ANTHROPIC_API_KEY) are
  STRIPPED from the OpenHarness subprocess environment (see Phase 7 sandbox).
- No secret values are recorded in this evidence file.

## Provenance verification method
- Version + license + requires-python read from installed METADATA.
- Wheel artifact hashes read from the installed dist-info RECORD (authoritative
  pip-recorded sha256 per file).
- PyPI index confirmed package exists at https://pypi.org/project/openharness-ai/
  (latest 0.1.9, requires_python >=3.10).
- No floating dependency: openharness-ai==0.1.9 pinned exactly; lockfile captured.

## Residual notes
- The `minimax-*` and `gpt-oss:120b-cloud` Ollama entries are cloud-routed model
  names; they are NOT used. Only the local `ornith-1.0-9b` model is used.
- OpenHarness default tool set includes write/shell/web tools; Gate A restricts
  the harness to read-only tools via configuration + sandbox (see Phase 3/7).
