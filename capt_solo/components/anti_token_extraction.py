"""CAPT Solo v0.4.1 Anti-Token-Extraction integration.

Optional, independently degradable capability. Invokes the REAL hardened
upstream package ``anti_token_extraction`` as a local child process over stdio
(FastMCP). No payload persistence, no historical retrieval, no credentials in
MCP arguments, cache mode off, sensitive-input refusal on.

Security properties preserved (per integration contract):

* stateless transformation by default,
* no persistent payload retention,
* no historical payload retrieval,
* no live credentials crossing MCP,
* stdio-only default transport,
* exact upstream provenance verification,
* independently degradable CAPT capability,
* no effect on memory, CTP, KHSB, governance, ClaimGuard, or plugin loading
  when unavailable.
"""

from __future__ import annotations

import asyncio
import importlib.metadata
import json
import os
import re
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from capt_solo.core.config import home_dir

UPSTREAM_REPO = "https://github.com/knowurknottty/anti-token-extraction"
PINNED_COMMIT = "b68adac7311b2315d992592b479e6761aa9dc856"
PINNED_VERSION = "0.2.0"
COMPONENT_ID = "anti-token-extraction"
DIST_NAME = "anti-token-extraction"

MAX_INPUT_BYTES = 1 * 1024 * 1024          # 1 MiB request bound (matches prior contract)
MAX_RESPONSE_BYTES = 4 * 1024 * 1024       # 4 MiB response line bound
INIT_TIMEOUT_SECONDS = 15.0
REQUEST_TIMEOUT_SECONDS = 30.0
MANIFEST_MAX_BYTES = 4096

# CAPT-side sensitive-input refusal (defense-in-depth, BEFORE transmission).
# Live validation against pinned upstream b68adac showed the upstream
# process_sensitive_input(policy="refuse") refuses AWS/GitHub/Bearer/PrivateKey
# but MISSES Slack (xoxb-) and Stripe (sk_live_) high-precision tokens. CAPT
# must refuse those at the boundary so they never cross MCP. Patterns are
# high-precision to avoid false positives on benign architectural text.
_SECRET_PATTERNS = (
    # Credential assignments (case-insensitive key=value / key: value)
    re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*\S+"),
    re.compile(r"(?i)(api[_-]?key|apikey|secret[_-]?key|access[_-]?token|"
               r"auth[_-]?token|client[_-]?secret|private[_-]?key|"
               r"refresh[_-]?token|session[_-]?token)\s*[:=]\s*\S+"),
    re.compile(r"(?i)(authorization|cookie|set-cookie)\s*:\s*\S+"),
    # High-precision bare tokens (refused before transmission)
    re.compile(r"AKIA[0-9A-Z]{16}"),                     # AWS access key ID
    re.compile(r"gh[pousr]_[0-9A-Za-z]{36}"),            # GitHub tokens
    re.compile(r"github_pat_[0-9A-Za-z_]{22,}"),         # GitHub fine-grained PAT
    re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}"),         # Slack tokens
    re.compile(r"sk_(live|test)_[0-9a-zA-Z]{24}"),       # Stripe secret keys
    re.compile(r"rk_(live|test)_[0-9a-zA-Z]{24}"),       # Stripe restricted keys
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+"),            # Bearer tokens
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
)


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


def is_sensitive_input(text: str) -> bool:
    """Refuse credential material before transmission.

    High-precision patterns: credential assignments (password=, api_key=, ...),
    bare tokens (AWS AKIA..., GitHub gh*, Slack xox*, Stripe sk_*, Bearer,
    private-key blocks). Refuses at the CAPT boundary so secrets never cross
    MCP to the upstream child process. False-positive risk is minimized by
    using high-precision token shapes rather than generic keyword matches.
    """
    return any(p.search(text) for p in _SECRET_PATTERNS)


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
        raw = path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return None
    if len(raw.encode("utf-8")) > MANIFEST_MAX_BYTES:
        return None
    try:
        return ATEManifest.from_dict(json.loads(raw))
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


def installed_provenance() -> Dict[str, Optional[str]]:
    """Read installed distribution provenance from direct_url.json.

    Returns version/commit/url/vcs. Absent fields are None (unverified).
    """
    try:
        dist = importlib.metadata.distribution(DIST_NAME)
    except importlib.metadata.PackageNotFoundError:
        return {"version": None, "commit": None, "url": None, "vcs": None}
    version = dist.version
    commit = None
    url = None
    vcs = None
    try:
        raw = dist.read_text("direct_url.json")
        if raw:
            direct = json.loads(raw)
            url = direct.get("url")
            vcs = (direct.get("vcs_info") or {}).get("vcs")
            commit = (direct.get("vcs_info") or {}).get("commit_id")
    except (OSError, ValueError, TypeError):
        pass
    return {"version": version, "commit": commit, "url": url, "vcs": vcs}


def _normalize_url(url: Optional[str]) -> str:
    if not url:
        return ""
    return url.rstrip("/").removesuffix(".git").rstrip().lower()


def _provenance_verified(prov: Dict[str, Optional[str]]) -> bool:
    if not prov.get("version") or not prov.get("commit") or not prov.get("url"):
        return False
    if prov["version"] != PINNED_VERSION:
        return False
    if prov["commit"] != PINNED_COMMIT:
        return False
    if (prov.get("vcs") or "").lower() != "git":
        return False
    return _normalize_url(prov["url"]) == _normalize_url(UPSTREAM_REPO)


def purge_legacy_cache() -> List[str]:
    """Invoke the upstream legacy-cache purge (no payload read, symlink-safe).

    The upstream removes ~/.cache/anti-token-extraction/csc2.json, refuses
    symlinks, and quarantines on failure. Returns a list of result summaries
    only for entries that were actually removed/quarantined (empty when absent).
    """
    try:
        from anti_token_extraction.tools import purge_legacy_cache as _upstream_purge
    except Exception:
        return []
    try:
        result = _upstream_purge()
        if isinstance(result, dict):
            # Only report when something was actually acted upon.
            if result.get("removed") or result.get("status") in ("removed", "quarantined"):
                return [str(result)]
            return []
        return [str(result)]
    except Exception:
        return []


def _build_transport():
    from fastmcp.client.transports import StdioTransport
    import sys
    return StdioTransport(command=sys.executable, args=["-m", "anti_token_extraction.server"])


async def _call_tool(tool: str, params: dict) -> str:
    from fastmcp import Client
    transport = _build_transport()
    async with Client(
        transport, timeout=REQUEST_TIMEOUT_SECONDS, init_timeout=INIT_TIMEOUT_SECONDS
    ) as client:
        try:
            result = await client.call_tool(tool, params)
        except Exception:
            # Restart on transient connection failure, then retry once.
            async with Client(
                transport, timeout=REQUEST_TIMEOUT_SECONDS, init_timeout=INIT_TIMEOUT_SECONDS
            ) as client2:
                result = await client2.call_tool(tool, params)
        parts: List[str] = []
        for item in getattr(result, "content", []) or []:
            item_type = getattr(item, "type", None)
            if item_type == "text" or hasattr(item, "text"):
                parts.append(getattr(item, "text", ""))
        output = "\n".join(parts)
        if len(output.encode("utf-8")) > MAX_RESPONSE_BYTES:
            raise UnsafeConfiguration("component response exceeds size limit")
        return output


def _compress_text(text: str, filter_name: str) -> str:
    return asyncio.run(_call_tool("rtk_compress", {"text": text, "filter_name": filter_name}))


def _detect_text(text: str) -> str:
    return asyncio.run(_call_tool("rtk_detect", {"text": text}))


async def _health_async() -> bool:
    from fastmcp import Client
    transport = _build_transport()
    async with Client(
        transport, timeout=REQUEST_TIMEOUT_SECONDS, init_timeout=INIT_TIMEOUT_SECONDS
    ) as client:
        tools = await client.list_tools()
        return any(getattr(t, "name", None) == "rtk_compress" for t in tools)


def _health_check_sync() -> bool:
    try:
        return asyncio.run(_health_async())
    except Exception:
        return False


def reset_client() -> None:
    """No-op kept for test-fixture symmetry; per-call clients need no reset."""
    return


async def _compress_async(text: str, filter_name: str) -> str:
    return await _call_tool("rtk_compress", {"text": text, "filter_name": filter_name})


async def _detect_async(text: str) -> str:
    return await _call_tool("rtk_detect", {"text": text})


class AntiTokenExtractionComponent:
    def __init__(self, manifest: Optional[ATEManifest] = None) -> None:
        self.manifest = manifest or load_manifest() or ATEManifest()

    def discover(self) -> Dict[str, Any]:
        prov = installed_provenance()
        manifest = load_manifest()
        safe_config = True
        try:
            _validate_manifest(self.manifest)
        except UnsafeConfiguration:
            safe_config = False
        installed = prov.get("version") is not None
        verified = _provenance_verified(prov)
        if not installed:
            state = "absent"
        elif not verified or not safe_config:
            state = "present-unverified"
        else:
            state = "present-ok"
        return {
            "component": COMPONENT_ID,
            "state": state,
            "manifest_present": manifest is not None,
            "pinned_commit": PINNED_COMMIT,
            "installed_commit": prov.get("commit"),
            "installed_version": prov.get("version"),
            "installed_url": prov.get("url"),
            "installed_vcs": prov.get("vcs"),
            "pinned_match": verified,
            "cache_mode": self.manifest.cache_mode,
            "sensitive_input_refusal": self.manifest.sensitive_input_refusal,
        }

    def verify_pinned_commit(self) -> bool:
        return _provenance_verified(installed_provenance())

    def bootstrap(self, force: bool = False) -> Dict[str, Any]:
        _validate_manifest(self.manifest)
        prov = installed_provenance()
        removed = purge_legacy_cache()
        verified = _provenance_verified(prov)
        if not verified:
            return {
                "bootstrapped": False,
                "idempotent": False,
                "healthy": False,
                "reason": "pinned upstream package provenance not verified",
                "legacy_cache_purged": removed,
                "installed_commit": prov.get("commit"),
                "provenance_verified": False,
            }
        prior = load_manifest()
        already_ok = (
            prior is not None
            and prior.installed_commit == PINNED_COMMIT
            and prior.installed_version == PINNED_VERSION
        )
        if already_ok and not force and not removed:
            return {
                "bootstrapped": False,
                "idempotent": True,
                "healthy": True,
                "legacy_cache_purged": [],
                "installed_commit": PINNED_COMMIT,
                "provenance_verified": True,
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
            "provenance_verified": True,
        }

    def health_check(self) -> Dict[str, Any]:
        discovery = self.discover()
        if discovery["state"] != "present-ok":
            return {
                "healthy": False,
                "state": discovery["state"],
                "reason": "package or pin unavailable",
            }
        try:
            ok = _health_check_sync()
            return {"healthy": ok, "state": discovery["state"], "reason": "" if ok else "rtk_compress tool missing"}
        except Exception as exc:
            return {"healthy": False, "state": discovery["state"], "reason": type(exc).__name__}

    def status(self) -> Dict[str, Any]:
        discovery = self.discover()
        health = self.health_check()
        return {
            **discovery,
            "healthy": health["healthy"],
            "health_reason": health.get("reason", ""),
            "pinned_verified": self.verify_pinned_commit(),
        }

    def compress(self, text: str, filter_name: str = "auto") -> Dict[str, Any]:
        if len(text.encode("utf-8")) > MAX_INPUT_BYTES:
            raise UnsafeConfiguration("input exceeds 1 MiB limit")
        if is_sensitive_input(text):
            raise UnsafeConfiguration("sensitive input refused: credential material detected")
        if self.discover()["state"] != "present-ok":
            raise ComponentUnavailable("pinned anti-token-extraction runtime is unavailable")
        try:
            output = _compress_text(text, filter_name)
        except (ComponentUnavailable, UnsafeConfiguration):
            raise
        except Exception as exc:
            raise ComponentUnavailable(f"compression failed: {type(exc).__name__}") from exc
        return {"ok": True, "output": output, "component": COMPONENT_ID, "filter": filter_name}

    def detect(self, text: str) -> Dict[str, Any]:
        """Deprecated but preserved: detect output type via upstream rtk_detect.

        Retained (not removed) so the capability is available for future use;
        the adapter's detect path is preserved here against the real upstream.
        Refuses sensitive input before transmission, same as compress().
        """
        if is_sensitive_input(text):
            raise UnsafeConfiguration("sensitive input refused: credential material detected")
        if self.discover()["state"] != "present-ok":
            raise ComponentUnavailable("pinned anti-token-extraction runtime is unavailable")
        try:
            output = _detect_text(text)
        except (ComponentUnavailable, UnsafeConfiguration):
            raise
        except Exception as exc:
            raise ComponentUnavailable(f"detection failed: {type(exc).__name__}") from exc
        return {"ok": True, "output": output, "component": COMPONENT_ID}

    def extract(self, text: str, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Deprecated alias. Compresses tool output; never extracts credentials."""
        return self.compress(text, filter_name="auto")


def bootstrap_anti_token_extraction(force: bool = False) -> Dict[str, Any]:
    return AntiTokenExtractionComponent().bootstrap(force=force)


def register_capability(reg) -> None:
    reg.register(
        COMPONENT_ID,
        description="Optional stateless tool-output compression over local stdio.",
        provider="anti-token-extraction",
        required_environment="local-child-process",
        dependencies=[f"anti-token-extraction=={PINNED_VERSION}"],
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
