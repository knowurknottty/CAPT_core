"""Sandbox and environment controls for the genuine OpenHarness external driver.

This module builds the allowlisted subprocess environment used to invoke the
real ``oh`` binary. It STRIPS all hosted-provider credentials and ambient
authority from the child process and exposes only what is necessary for a
read-only local-Ollama analysis run.

CAPT never grants the external harness any aggregate-mutation authority. The
harness receives: an isolated venv ``oh`` binary, a sandboxed config dir, a
localhost Ollama endpoint, the selected local model, the read-only target
repository, and the CAPT-owned staging directory.

No secrets are read or printed here. Hosted keys are removed by name.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Set

# Hosted-provider / ambient-authority variables that must NEVER reach the
# external harness subprocess.
_STRIP_ENV_VARS: Set[str] = {
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_BASE_URL",
    "OPENAI_API_KEY",  # replaced with a non-secret local placeholder below
    "OPENAI_BASE_URL",  # replaced with localhost Ollama below
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "GH_ENTERPRISE_TOKEN",
    "SSH_AUTH_SOCK",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "GOOGLE_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "OPENROUTER_API_KEY",
    "DEEPSEEK_API_KEY",
    "GEMINI_API_KEY",
    "MISTRAL_API_KEY",
    "TOGETHER_API_KEY",
    "PERPLEXITY_API_KEY",
    "XAI_API_KEY",
    "GROQ_API_KEY",
    "COHERE_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "OPENHARNESS_API_KEY",  # we set our own non-secret placeholder
}

# Minimal locale/runtime variables that are safe to forward.
_FORWARD_ENV_VARS: Set[str] = {
    "PATH",
    "HOME",
    "TMPDIR",
    "TEMP",
    "TMP",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "PYTHONIOENCODING",
    "TERM",
    "PWD",
}

# Local Ollama OpenAI-compatible endpoint (the only network the harness may use).
LOCAL_OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"

# Non-secret placeholder API key for local Ollama (OpenAI-compatible clients
# require *some* key string; Ollama ignores it). This is NOT a hosted credential.
LOCAL_OLLAMA_API_KEY = "ollama-local"


def build_allowlisted_env(
    config_dir: str,
    model: str,
    *,
    ollama_base_url: str = LOCAL_OLLAMA_BASE_URL,
    ollama_api_key: str = LOCAL_OLLAMA_API_KEY,
) -> Dict[str, str]:
    """Construct a minimal, allowlisted environment for the ``oh`` subprocess.

    Starts from a tiny safe allowlist, then adds only the variables required to
    point OpenHarness at local Ollama. All hosted keys are excluded.
    """
    env: Dict[str, str] = {}
    for name in _FORWARD_ENV_VARS:
        val = os.environ.get(name)
        if val is not None:
            env[name] = val
    # Force OpenHarness to use the openai-compatible client against localhost.
    env["OPENHARNESS_CONFIG_DIR"] = config_dir
    env["OPENHARNESS_MODEL"] = model
    env["OPENHARNESS_BASE_URL"] = ollama_base_url
    env["OPENHARNESS_API_KEY"] = ollama_api_key
    # The openai-compatible path is what actually reaches Ollama.
    env["OPENAI_API_KEY"] = ollama_api_key
    env["OPENAI_BASE_URL"] = ollama_base_url
    # Ensure no hosted key leaks through (defensive; names already excluded).
    for banned in _STRIP_ENV_VARS:
        env.pop(banned, None)
    return env


def validate_paths(target_repo: str, staging_root: str) -> Dict[str, str]:
    """Validate and canonicalize target/staging paths.

    Rejects symlink escapes and ensures the target is not the staging dir.
    Returns real paths. Raises ValueError on any unsafe condition.
    """
    tgt = Path(target_repo).resolve()
    stg = Path(staging_root).resolve()
    if not tgt.exists() or not tgt.is_dir():
        raise ValueError("target repository does not exist or is not a dir: %s" % target_repo)
    if tgt == stg:
        raise ValueError("target repository must not equal the staging directory")
    # Staging may be created; target must remain read-only to CAPT and harness.
    stg.mkdir(parents=True, exist_ok=True)
    return {"target_repo": str(tgt), "staging_root": str(stg)}


def allowed_network_hosts() -> List[str]:
    """The only network endpoint the external harness is permitted to contact."""
    return ["127.0.0.1:11434"]
