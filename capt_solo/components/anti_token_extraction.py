"""CAPT Solo v0.4.1 Anti-Token-Extraction integration.

The component is optional and independently degradable. It launches a local
stdio adapter which imports the pinned upstream package. No payload persistence,
network transport, historical retrieval, or credential-bearing arguments are
permitted.
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import selectors
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from capt_solo.core.config import home_dir

UPSTREAM_REPO = "https://github.com/knowurknottty/anti-token-extraction"
PINNED_COMMIT = "b68adac7311b2315d992592b479e6761aa9dc856"
PINNED_VERSION = "0.2.0"
COMPONENT_ID = "anti-token-extraction"
MAX_REQUEST_BYTES = 1_048_576
LEGACY_CACHE_NAMES = ("ate_cache", ".ate_cache", "anti_token_cache", "token_extract_cache")


class ComponentUnavailable(Exception):
    """The optional component cannot safely serve the request."""


class UnsafeConfiguration(Exception):
    """A hard component safety constraint was violated."""


@dataclass
class ATEManifest:
    component: str = COMPONENT_ID
    upstream_repo: str = UPSTREAM_REPO
    pinned_commit: str = PINNED_COMMIT
    pinned_version: str = PINNED_VERSION
    cache_mode: str = "off"
    sensitive_input_refusal: bool = True
    transport: str = "local-child-process-stdio"
    no_credentials_in_args: bool = True
    installed_commit: Optional[str] = None
    installed_version: Optional[str] = None
    bootstrapped_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "ATEManifest":
        fields = cls.__dataclass_fields__
        return cls(**{key: item for key, item in value.items() if key in fields})


def component_dir() -> Path:
    return Path(__file__).resolve().parent


def manifest_path() -> Path:
    override = os.environ.get("CAPT_ATE_MANIFEST_PATH")
    if override:
        return Path(override)
    return home_dir() / "components" / COMPONENT_ID / "manifest.json"


def stdio_server_path() -> Path:
    return component_dir() / "_ate_stdio_server.py"


def legacy_cache_dirs() -> List[Path]:
    root = home_dir()
    paths = [root / name for name in LEGACY_CACHE_NAMES]
    paths.append(Path.home() / ".cache" / "anti-token-extraction")
    return paths


def _validate_manifest(manifest: ATEManifest) -> None:
    if manifest.cache_mode != "off":
        raise UnsafeConfiguration("cache_mode must be 'off'")
    if not manifest.sensitive_input_refusal:
        raise UnsafeConfiguration("sensitive_input_refusal must be enabled")
    if not manifest.no_credentials_in_args:
        raise UnsafeConfiguration("credentials in process arguments are forbidden")
    if manifest.transport != "local-child-process-stdio":
        raise UnsafeConfiguration("only local child-process stdio is supported")
    if manifest.pinned_commit != PINNED_COMMIT or manifest.pinned_version != PINNED_VERSION:
        raise UnsafeConfiguration("component pin does not match the release policy")


def load_manifest() -> Optional[ATEManifest]:
    path = manifest_path()
    if not path.is_file() or path.is_symlink():
        return None
    try:
        return ATEManifest.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return None


def save_manifest(manifest: ATEManifest) -> None:
    _validate_manifest(manifest)
    path = manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise UnsafeConfiguration("manifest path must not be a symlink")
    payload = json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=".manifest-", dir=str(path.parent), text=True)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
        if os.name == "posix":
            os.chmod(path, 0o600)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def purge_legacy_cache() -> List[str]:
    removed: List[str] = []
    for path in legacy_cache_dirs():
        if path.is_symlink():
            continue
        if path.is_dir():
            shutil.rmtree(path)
            removed.append(str(path))
        elif path.is_file():
            path.unlink()
            removed.append(str(path))
    return removed


def installed_provenance() -> Dict[str, Optional[str]]:
    try:
        dist = importlib.metadata.distribution("anti-token-extraction")
    except importlib.metadata.PackageNotFoundError:
        return {"version": None, "commit": None, "url": None}
    commit = None
    url = None
    try:
        raw = dist.read_text("direct_url.json")
        if raw:
            direct = json.loads(raw)
            url = direct.get("url")
            commit = (direct.get("vcs_info") or {}).get("commit_id")
    except (OSError, ValueError, TypeError):
        pass
    return {"version": dist.version, "commit": commit, "url": url}


def _provenance_matches(provenance: Dict[str, Optional[str]]) -> bool:
    return provenance.get("version") == PINNED_VERSION and provenance.get("commit") == PINNED_COMMIT


def _spawn_server() -> subprocess.Popen[str]:
    server = stdio_server_path()
    if not server.is_file() or server.is_symlink():
        raise ComponentUnavailable("component stdio adapter is unavailable")
    proc = subprocess.Popen(
        [sys.executable, "-I", str(server), "--cache-mode", "off", "--refusal", "on"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        close_fds=True,
    )
    if proc.stdin is None or proc.stdout is None:
        proc.kill()
        raise ComponentUnavailable("stdio pipes were not created")
    return proc


def _jsonrpc(
    proc: subprocess.Popen[str], method: str, params: Dict[str, Any], timeout: float = 5.0
) -> Dict[str, Any]:
    if proc.stdin is None or proc.stdout is None:
        raise ComponentUnavailable("stdio channel unavailable")
    message = json.dumps(
        {"jsonrpc": "2.0", "id": uuid.uuid4().hex, "method": method, "params": params},
        separators=(",", ":"),
    )
    if len(message.encode("utf-8")) > MAX_REQUEST_BYTES + 4096:
        raise UnsafeConfiguration("request exceeds 1 MiB limit")
    try:
        proc.stdin.write(message + "\n")
        proc.stdin.flush()
        selector = selectors.DefaultSelector()
        selector.register(proc.stdout, selectors.EVENT_READ)
        if not selector.select(timeout):
            raise ComponentUnavailable("stdio response timed out")
        line = proc.stdout.readline()
        if not line:
            raise ComponentUnavailable("stdio server closed the channel")
        response = json.loads(line)
    except (BrokenPipeError, OSError, ValueError) as exc:
        raise ComponentUnavailable(f"stdio communication failed: {exc}") from exc
    finally:
        try:
            selector.close()
        except UnboundLocalError:
            pass
    if response.get("error"):
        message = str(response["error"].get("message", "component error"))
        if "sensitive" in message.lower():
            raise UnsafeConfiguration("sensitive input refused by upstream policy")
        raise ComponentUnavailable(message)
    result = response.get("result", {})
    if not isinstance(result, dict):
        raise ComponentUnavailable("invalid component response")
    return result


def _stop(proc: Optional[subprocess.Popen[str]]) -> None:
    if proc is None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=2)
    except Exception:
        proc.kill()
        proc.wait(timeout=2)


class AntiTokenExtractionComponent:
    def __init__(self, manifest: Optional[ATEManifest] = None) -> None:
        self.manifest = manifest or load_manifest() or ATEManifest()

    def discover(self) -> Dict[str, Any]:
        provenance = installed_provenance()
        manifest = load_manifest()
        safe_config = True
        try:
            _validate_manifest(self.manifest)
        except UnsafeConfiguration:
            safe_config = False
        installed = provenance.get("version") is not None
        pinned = _provenance_matches(provenance)
        if not installed:
            state = "absent"
        elif not pinned or manifest is None or not safe_config:
            state = "present-mismatch"
        else:
            state = "present-ok"
        return {
            "component": COMPONENT_ID,
            "state": state,
            "server_present": stdio_server_path().is_file(),
            "manifest_present": manifest is not None,
            "pinned_commit": PINNED_COMMIT,
            "installed_commit": provenance.get("commit"),
            "installed_version": provenance.get("version"),
            "pinned_match": pinned,
            "cache_mode": self.manifest.cache_mode,
            "sensitive_input_refusal": self.manifest.sensitive_input_refusal,
        }

    def verify_pinned_commit(self) -> bool:
        return _provenance_matches(installed_provenance())

    def bootstrap(self, force: bool = False) -> Dict[str, Any]:
        _validate_manifest(self.manifest)
        provenance = installed_provenance()
        removed = purge_legacy_cache()
        if not _provenance_matches(provenance):
            return {
                "bootstrapped": False,
                "idempotent": False,
                "healthy": False,
                "reason": "pinned upstream package is not installed",
                "legacy_cache_purged": removed,
                "installed_commit": provenance.get("commit"),
            }
        prior = load_manifest()
        already_ok = prior is not None and prior.installed_commit == PINNED_COMMIT
        if already_ok and not force and not removed:
            return {
                "bootstrapped": False,
                "idempotent": True,
                "healthy": True,
                "legacy_cache_purged": [],
                "installed_commit": PINNED_COMMIT,
            }
        self.manifest.installed_commit = PINNED_COMMIT
        self.manifest.installed_version = PINNED_VERSION
        self.manifest.bootstrapped_at = time.time()
        save_manifest(self.manifest)
        return {
            "bootstrapped": True,
            "idempotent": False,
            "healthy": True,
            "legacy_cache_purged": removed,
            "installed_commit": PINNED_COMMIT,
        }

    def health_check(self) -> Dict[str, Any]:
        discovery = self.discover()
        if discovery["state"] != "present-ok":
            return {"healthy": False, "state": discovery["state"], "reason": "package or pin unavailable"}
        proc = None
        try:
            proc = _spawn_server()
            _jsonrpc(proc, "initialize", {})
            result = _jsonrpc(proc, "health", {})
            return {"healthy": bool(result.get("ok")), "state": discovery["state"], "reason": result.get("detail", "")}
        except (ComponentUnavailable, UnsafeConfiguration) as exc:
            return {"healthy": False, "state": discovery["state"], "reason": str(exc)}
        finally:
            _stop(proc)

    def status(self) -> Dict[str, Any]:
        discovery = self.discover()
        health = self.health_check()
        return {**discovery, "healthy": health["healthy"], "health_reason": health.get("reason", ""), "pinned_verified": self.verify_pinned_commit()}

    def compress(self, text: str, filter_name: str = "auto") -> Dict[str, Any]:
        if len(text.encode("utf-8")) > MAX_REQUEST_BYTES:
            raise UnsafeConfiguration("input exceeds 1 MiB limit")
        _validate_manifest(self.manifest)
        if self.discover()["state"] != "present-ok":
            raise ComponentUnavailable("pinned anti-token-extraction runtime is unavailable")
        proc = None
        try:
            proc = _spawn_server()
            _jsonrpc(proc, "initialize", {})
            result = _jsonrpc(proc, "compress", {"text": text, "filter_name": filter_name})
            return {"ok": True, "component": COMPONENT_ID, **result}
        finally:
            _stop(proc)

    def extract(self, text: str, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Backward-compatible alias. This compresses tool output; it never extracts credentials."""
        return self.compress(text, filter_name="auto")


def bootstrap_anti_token_extraction(force: bool = False) -> Dict[str, Any]:
    return AntiTokenExtractionComponent().bootstrap(force=force)


def register_capability(reg) -> None:
    reg.register(
        COMPONENT_ID,
        description="Optional stateless tool-output compression over local stdio.",
        provider="anti-token-extraction",
        required_environment="local-child-process",
        dependencies=["anti-token-extraction==0.2.0"],
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
