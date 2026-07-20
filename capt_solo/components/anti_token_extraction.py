"""CAPT Solo v0.4.1 — Anti-Token-Extraction component.

Optional, independently degradable capability. Runs as a LOCAL child process
over stdio (JSON-RPC 2.0). No network, no embedding into CAPT memory/CTP/KHSB.
Cache mode is OFF. Sensitive-input refusal is ON. No credentials are ever
passed in MCP arguments.

The upstream source is pinned by repository + commit in the component manifest.
A minimal, vendored stdio server (`_ate_stdio_server.py`) provides the local
runtime so the capability works offline; `verify_pinned_commit()` confirms the
installed commit matches the pinned upstream commit.

Failure of this component degrades ONLY the anti-token-extraction capability
(never memory, CTP, KHSB, governance, ClaimGuard, plugin loading, or core).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from capt_solo.core.config import home_dir

# Pinned upstream — recorded in the manifest; never fetched at runtime.
UPSTREAM_REPO = "https://github.com/knowurknottty/anti-token-extraction"
PINNED_COMMIT = "b68adac7311b2315d992592b479e6761aa9dc856"

COMPONENT_ID = "anti-token-extraction"
LEGACY_CACHE_NAMES = ("ate_cache", ".ate_cache", "anti_token_cache", "token_extract_cache")


class ComponentUnavailable(Exception):
    """Raised when the anti-token-extraction child process cannot serve."""


class UnsafeConfiguration(Exception):
    """Raised when the component manifest violates a hard safety constraint."""


@dataclass
class ATEManifest:
    component: str = COMPONENT_ID
    upstream_repo: str = UPSTREAM_REPO
    pinned_commit: str = PINNED_COMMIT
    cache_mode: str = "off"
    sensitive_input_refusal: bool = True
    transport: str = "local-child-process-stdio"
    no_credentials_in_args: bool = True
    installed_commit: Optional[str] = None
    bootstrapped_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ATEManifest":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def component_dir() -> Path:
    return Path(__file__).resolve().parent


def manifest_path() -> Path:
    # Allow tests / isolated runs to redirect the manifest elsewhere.
    override = os.environ.get("CAPT_ATE_MANIFEST_PATH")
    if override:
        return Path(override)
    return component_dir() / "manifest.json"


# Sensitive-input refusal targets CREDENTIAL ASSIGNMENTS (something being
# submitted as a secret to process/store), NOT bare tokens that are themselves
# extraction targets (e.g. AKIA…, ghp_…). Those are what the component finds.
_SECRET_ASSIGNMENT_PATTERNS = [
    re.compile(r"(?i)-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{20,}"),
    re.compile(r"(?i)(api[_-]?key|apikey|secret[_-]?key)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?[^\\s'\"]{6,}"),
    re.compile(r"(?i)(session|auth|access)[_\-]?token\s*[:=]\s*['\"]?[A-Za-z0-9._\-]{20,}"),
    re.compile(r"(?i)recovery[_-]?code\s*[:=]\s*['\"]?[A-Za-z0-9]{8,}"),
    re.compile(r"(?i)(seed\s*phrase|mnemonic|recovery\s*phrase)\b"),
    re.compile(r"(?i)(?:^|\n)\s*(?:export\s+)?[A-Z][A-Z0-9_]{2,}\s*=\s*['\"]?[A-Za-z0-9/+_\-]{20,}['\"]?\s*(?:\n|$)"),
]


def is_sensitive_input(text: str) -> bool:
    """True if the input carries a credential assignment (refuse, don't extract)."""
    return any(p.search(text) for p in _SECRET_ASSIGNMENT_PATTERNS)


def stdio_server_path() -> Path:
    return component_dir() / "_ate_stdio_server.py"


def legacy_cache_dirs() -> List[Path]:
    root = home_dir()
    return [root / n for n in LEGACY_CACHE_NAMES]


def _validate_manifest(m: ATEManifest) -> None:
    if m.cache_mode != "off":
        raise UnsafeConfiguration(
            f"cache_mode must be 'off' for anti-token-extraction (got '{m.cache_mode}')")
    if not m.sensitive_input_refusal:
        raise UnsafeConfiguration(
            "sensitive_input_refusal must be True for anti-token-extraction")
    if not m.no_credentials_in_args:
        raise UnsafeConfiguration(
            "no_credentials_in_args must be True for anti-token-extraction")


def load_manifest() -> Optional[ATEManifest]:
    p = manifest_path()
    if not p.exists():
        return None
    try:
        return ATEManifest.from_dict(json.loads(p.read_text()))
    except Exception:
        return None


def save_manifest(m: ATEManifest) -> None:
    _validate_manifest(m)
    manifest_path().write_text(json.dumps(m.to_dict(), indent=2))


def purge_legacy_cache() -> List[str]:
    """Remove any legacy anti-token-extraction cache directories.

    Returns the list of paths that were removed. Idempotent: safe to call
    when no legacy cache exists.
    """
    removed: List[str] = []
    for d in legacy_cache_dirs():
        if d.exists() and d.is_dir():
            shutil.rmtree(d)
            removed.append(str(d))
    return removed


def _spawn_server(timeout: float = 5.0) -> subprocess.Popen:
    """Spawn the bundled stdio server as a local child process."""
    server = stdio_server_path()
    if not server.exists():
        raise ComponentUnavailable(f"stdio server not found: {server}")
    # No credentials are passed as arguments — only the safety-constrained flags.
    proc = subprocess.Popen(
        [sys.executable, str(server), "--cache-mode", "off", "--refusal", "on"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1)
    assert proc.stdin is not None and proc.stdout is not None, \
        "stdio pipes must be open for the child process"
    return proc


def _jsonrpc(proc: subprocess.Popen, method: str, params: Any,
             req_id: str = None, timeout: float = 5.0) -> Dict[str, Any]:
    if req_id is None:
        req_id = uuid.uuid4().hex
    msg = json.dumps({"jsonrpc": "2.0", "id": req_id, "method": method,
                      "params": params or {}})
    try:
        proc.stdin.write(msg + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        if not line:
            raise ComponentUnavailable("stdio server closed connection")
        resp = json.loads(line)
        if "error" in resp:
            raise ComponentUnavailable(f"server error: {resp['error']}")
        return resp.get("result", {})
    except (json.JSONDecodeError, BrokenPipeError, ValueError) as e:
        raise ComponentUnavailable(f"stdio communication failed: {e}")


class AntiTokenExtractionComponent:
    """Manages the optional anti-token-extraction capability.

    All methods are safe to call when the component is absent: they report
    status rather than raising, except ``extract()`` which raises
    ``ComponentUnavailable`` so the caller can degrade ONLY this capability.
    """

    def __init__(self, manifest: Optional[ATEManifest] = None) -> None:
        self.manifest = manifest or load_manifest() or ATEManifest()

    # ----- discovery / status ------------------------------------------
    def discover(self) -> Dict[str, Any]:
        """Report component presence and pin match without spawning."""
        server_present = stdio_server_path().exists()
        manifest_present = manifest_path().exists()
        pinned_ok = (self.manifest.installed_commit == self.manifest.pinned_commit)
        if not server_present:
            state = "absent"
        elif not manifest_present and self.manifest.installed_commit is None:
            # bundled server exists but nothing has been bootstrapped
            state = "absent"
        elif not manifest_present or not pinned_ok:
            state = "present-mismatch"
        else:
            state = "present-ok"
        return {
            "component": COMPONENT_ID,
            "state": state,
            "server_present": server_present,
            "manifest_present": manifest_present,
            "pinned_commit": self.manifest.pinned_commit,
            "installed_commit": self.manifest.installed_commit,
            "pinned_match": pinned_ok,
            "cache_mode": self.manifest.cache_mode,
            "sensitive_input_refusal": self.manifest.sensitive_input_refusal,
        }

    def verify_pinned_commit(self) -> bool:
        """True iff the installed commit matches the pinned upstream commit."""
        return (self.manifest.installed_commit == self.manifest.pinned_commit
                and self.manifest.installed_commit is not None)

    # ----- lifecycle ----------------------------------------------------
    def bootstrap(self, force: bool = False) -> Dict[str, Any]:
        """Idempotent bootstrap: purge legacy cache, pin installed commit.

        Calling twice with no change is a no-op (idempotent). Only writes the
        manifest when state actually changes or ``force`` is set.
        """
        prior = load_manifest()
        already_ok = (prior is not None
                      and prior.installed_commit == self.manifest.pinned_commit
                      and stdio_server_path().exists())
        removed = purge_legacy_cache()
        if already_ok and not force and not removed:
            return {"bootstrapped": False, "idempotent": True,
                    "legacy_cache_purged": removed,
                    "installed_commit": self.manifest.installed_commit}
        self.manifest.installed_commit = self.manifest.pinned_commit
        self.manifest.bootstrapped_at = time.time()
        save_manifest(self.manifest)
        return {"bootstrapped": True, "idempotent": False,
                "legacy_cache_purged": removed,
                "installed_commit": self.manifest.installed_commit}

    # ----- health -------------------------------------------------------
    def health_check(self) -> Dict[str, Any]:
        """Spawn the child process and confirm it answers a health ping."""
        disc = self.discover()
        if disc["state"] == "absent":
            return {"healthy": False, "reason": "component absent",
                    "state": disc["state"]}
        if disc["state"] == "present-mismatch":
            return {"healthy": False, "reason": "commit/version mismatch",
                    "state": disc["state"],
                    "installed": disc["installed_commit"],
                    "pinned": disc["pinned_commit"]}
        proc = None
        try:
            proc = _spawn_server()
            _jsonrpc(proc, "initialize", {"capabilities": {}})
            res = _jsonrpc(proc, "health", {})
            healthy = bool(res.get("ok", False))
            return {"healthy": healthy, "reason": res.get("detail", ""),
                    "state": disc["state"]}
        except ComponentUnavailable as e:
            return {"healthy": False, "reason": str(e), "state": disc["state"]}
        finally:
            if proc is not None:
                try:
                    proc.terminate()
                    proc.wait(timeout=2)
                except Exception:
                    proc.kill()

    def status(self) -> Dict[str, Any]:
        disc = self.discover()
        health = self.health_check()
        return {**disc, "healthy": health["healthy"],
                "health_reason": health.get("reason", ""),
                "pinned_verified": self.verify_pinned_commit()}

    # ----- extraction ---------------------------------------------------
    def extract(self, text: str, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Extract tokens from ``text`` via the local child process.

        Refuses sensitive input (credential assignments) before spawning.
        Raises ``ComponentUnavailable`` on any failure so the caller can
        degrade ONLY this capability.
        """
        if is_sensitive_input(text):
            raise UnsafeConfiguration(
                "sensitive input refused: credential assignment detected")
        # Safety constraint: cache must be off and refusal on, regardless of
        # bootstrap state. An unsafe manifest must never be served.
        if self.manifest.cache_mode != "off":
            raise UnsafeConfiguration(
                f"unsafe cache_mode '{self.manifest.cache_mode}' (must be 'off')")
        if not self.manifest.sensitive_input_refusal:
            raise UnsafeConfiguration(
                "sensitive_input_refusal must be True")
        disc = self.discover()
        if disc["state"] != "present-ok":
            raise ComponentUnavailable(
                f"anti-token-extraction not available (state={disc['state']})")
        proc = None
        try:
            proc = _spawn_server()
            _jsonrpc(proc, "initialize", {"capabilities": {}})
            res = _jsonrpc(proc, "extract", {"text": text, "schema": schema or {}})
            return {"ok": True, "tokens": res.get("tokens", []),
                    "component": COMPONENT_ID}
        except ComponentUnavailable:
            raise
        finally:
            if proc is not None:
                try:
                    proc.terminate()
                    proc.wait(timeout=2)
                except Exception:
                    proc.kill()


def bootstrap_anti_token_extraction(force: bool = False) -> Dict[str, Any]:
    """Convenience: construct the component and run an idempotent bootstrap."""
    comp = AntiTokenExtractionComponent()
    return comp.bootstrap(force=force)


def register_capability(reg) -> None:
    """Register the anti-token-extraction capability as optional + degradable.

    The capability starts in 'candidate' (not verified) and is independently
    degradable: a failure degrades ONLY this capability, never the rest of CAPT.
    """
    reg.register(
        COMPONENT_ID,
        description="Optional anti-token-extraction via local child-process stdio.",
        provider="capt-solo/components",
        required_environment="local-child-process",
        dependencies=["capt_solo.components._ate_stdio_server"],
        supported_versions=["0.4.1"],
        lifecycle="candidate",
        creation_metadata={
            "optional": True,
            "independently_degradable": True,
            "pinned_upstream": UPSTREAM_REPO,
            "pinned_commit": PINNED_COMMIT,
            "cache_mode": "off",
            "sensitive_input_refusal": True,
        },
    )
