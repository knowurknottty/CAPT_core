# Gate A — Phase 2/3 Feasibility Proof Evidence

## Phase 2 — Headless OpenHarness execution (no-tool prompt)

- Command (sandboxed env, stripped hosted keys):
  OPENHARNESS_CONFIG_DIR=/tmp/oh-home \
  OPENHARNESS_MODEL="ornith-1.0-9b" \
  OPENHARNESS_BASE_URL="http://127.0.0.1:11434/v1" \
  OPENHARNESS_API_KEY="ollama-local" \
  oh -p "Respond with exactly: OPENHARNESS_LOCAL_EXECUTION_OK" --output-format text --max-turns 1
- Exit code: 0
- Elapsed: 8.48s
- stdout: `OPENHARNESS_LOCAL_EXECUTION_OK`
- stderr: (empty)
- OpenHarness version: 0.1.9 (genuine `oh` binary from openharness-ai wheel)
- Ollama received: `POST /v1/chat/completions` to 127.0.0.1:11434, model ornith-1.0-9b
- Network: only localhost Ollama. No hosted provider contacted.
- Config mechanism required: `OPENHARNESS_CONFIG_DIR` pointing at a settings.json
  with `api_format: "openai"` (OpenHarness defaults api_format to "anthropic"
  and ignores OPENHARNESS_BASE_URL unless api_format is forced to openai).

## Phase 3 — Read-only repository analysis (real tools)

- Fixture repo: /tmp/fixture_repo (4 files: README.md, pkg/__init__.py,
  pkg/core.py, pkg/sub/util.py). Git-initialized, no secrets.
- Before digest (sha256 over sorted file shasums):
  880a5f1b4dac6638047671a9821d2b8010e9e4089f3cc5e0f217e451693ede06
- Command:
  cd /tmp/fixture_repo
  OPENHARNESS_CONFIG_DIR=/tmp/oh-home OPENHARNESS_MODEL="ornith-1.0-9b" \
  OPENHARNESS_BASE_URL="http://127.0.0.1:11434/v1" OPENHARNESS_API_KEY="ollama-local" \
  oh -p "<read-only analysis prompt>" --output-format text --max-turns 4 --permission-mode default
- Exit code: 0, Elapsed: 15.65s
- OpenHarness output (verbatim, saved: gate-a-evidence/phase3_fixture_analysis.txt):
  - Described package architecture (3 files, single re-exported process()).
  - Identified SQL injection at pkg/core.py:7 (intentional injected defect) AND
    bare except at pkg/core.py:12.
  - Both observations are evidence-backed (correct file + line).
- After digest: 880a5f1b4dac6638047671a9821d2b8010e9e4089f3cc5e0f217e451693ede06
- REPO_UNCHANGED: YES (identical digests)
- Fixture tree after: identical 4 files, no new artifacts, no writes.
- Tool restriction: `--permission-mode default` in non-interactive --print mode
  denies write/shell tools (no approval possible); harness performed only reads.

## Phase 4 — Feasibility decision

Result: **OPENHARNESS_FEASIBILITY_PROVEN**

Satisfied requirements:
- genuine OpenHarness process executed (oh 0.1.9 subprocess, exit 0)
- local Ollama model executed (ornith-1.0-9b, POST /v1/chat/completions)
- non-interactive result captured (stdout)
- real read-only repository analysis completed (identified exact defects)
- repository remained unchanged (identical digest)
- tool restrictions demonstrated (default permission mode; no write/shell)
- no unrelated credentials or network authority exposed (hosted keys stripped;
  only localhost Ollama contacted)

OpenHarness is selected as the Gate A external harness. Proceed to adapter
implementation (Phases 5-6).
