# Source & License Evidence — OpenHarness (Gate A)

## Upstream

- Project: OpenHarness
- Canonical repository: https://github.com/HKUDS/OpenHarness
- License: MIT (License-Expression: MIT)
- Description: open-source Python agent harness (tool-use, skills, memory,
  multi-agent coordination).

## Package

- Distribution name: `openharness-ai`
- Exact version: **0.1.9**
- PyPI: https://pypi.org/project/openharness-ai/0.1.9/
- Python requirement: `>=3.10`
- Console scripts: `oh`, `ohmo`, `openh`
- Installed location (isolated venv):
  `/Users/knowurknot/capt-m0a-gatea/.venv-external/lib/python3.12/site-packages/openharness`

## Wheel artifact hashes (from installed dist-info RECORD)

- `bin/oh`    sha256=MPcHSj3WvJlpohON3zcgGf1yx043lRnI0_idgs95PpM
- `bin/ohmo`  sha256=Gr2S7l21_FFVU2ObugycePszSipFHmN65CIPU5mmQaM
- `bin/openh` sha256=MPcHSj3WvJlpohON3zcgGf1yx043lRnI0_idgs95PpM

(These are the pip-recorded sha256 values for the installed wheel files.)

## Dependency lock

- Lockfile: `external_driver_requirements.lock` (pip freeze, 77 packages) at repo
  root of the Gate A worktree.
- Resolution: OpenHarness 0.1.9 pulled its pinned dependency tree; no floating
  `main`/`latest`/unpinned git URL was used. Version pinned exactly.

## Installation method

- Isolated venv: `/opt/homebrew/bin/python3.12 -m venv .venv-external`
- `pip install openharness-ai==0.1.9` (pinned)
- No global installation; system Python 3.9.6 unchanged.

## Local modifications

- NONE. The openharness package is installed unmodified from PyPI.
- CAPT does NOT vendor or copy any OpenHarness source into the repository. The
  adapter only shells out to the `oh` binary.

## Vendored code

- None copied into CAPT.

## Update policy

- Pinned at 0.1.9 for Gate A reproducibility. Future bumps require re-running
  provenance capture and re-verifying the feasibility proof.

## Known security advisories

- None specific to 0.1.9 identified at integration time. The harness is run with
  least authority (stripped env, read-only task, localhost-only network).

## Hosted-service dependency

- NONE at runtime. OpenHarness is pointed at a LOCAL Ollama OpenAI-compatible
  endpoint (`http://127.0.0.1:11434/v1`) with a local model (`ornith-1.0-9b`).
  No Anthropic/OpenAI/hosted API is contacted; no hosted key is provided.

## License compliance

- MIT permits CAPT's use as an external subprocess and the adapter code. No
  upstream code is redistributed by CAPT.
