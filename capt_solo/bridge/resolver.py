"""Canonical CAPT source + executable resolution for the bootstrap bridge.

Resolution is *evidence-based*: a CAPT installation is only accepted when it
actually contains the Agent Runner. The baseline for this mission proved why —
the pip-installed ``capt_solo`` on the acceptance host reports ``__version__ ==
"0.5.0"`` and imports cleanly, but has **no** ``capt_solo/agent/`` package at all.
An importability check alone would have selected a runner-less CAPT and produced a
convincing false positive.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

# Modules that must exist for a CAPT tree to be able to boot an Agent Runner.
REQUIRED_AGENT_MODULES: Tuple[str, ...] = (
    "capt_solo/agent/__init__.py",
    "capt_solo/agent/boot.py",
    "capt_solo/agent/runner.py",
    "capt_solo/agent/contracts.py",
    "capt_solo/model_task.py",
)

# Environment variables that may be forwarded to the runner. Everything else is
# dropped: the runner does not inherit the full parent environment.
_ENV_ALLOWLIST: Tuple[str, ...] = (
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "TMPDIR",
    "CAPT_HOME",
    "CAPT_MODEL_ENDPOINT",
    "CAPT_MODEL_ID",
    "CAPT_EVIDENCE_DIR",
    "PYTHONPATH",
    "SSL_CERT_FILE",
)

# Credential-bearing variables forwarded by *name* only when present. Their values
# are never logged, echoed, hashed, or placed in argv.
_ENV_SECRET_ALLOWLIST: Tuple[str, ...] = (
    "LM_STUDIO_API_KEY",
    "CAPT_MODEL_API_KEY",
)


@dataclass
class CaptSource:
    """A resolved CAPT installation and how to invoke it."""

    root: Path
    launch_argv: Tuple[str, ...]
    launch_kind: str  # "console_entrypoint" | "module_fallback"
    version: str = ""
    missing_modules: Tuple[str, ...] = ()
    notes: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def complete(self) -> bool:
        return not self.missing_modules


def _missing_agent_modules(root: Path) -> Tuple[str, ...]:
    return tuple(rel for rel in REQUIRED_AGENT_MODULES if not (root / rel).is_file())


def _read_version(root: Path) -> str:
    init = root / "capt_solo" / "__init__.py"
    try:
        for line in init.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("__version__"):
                return line.split("=", 1)[1].strip().strip("\"'")
    except Exception:
        pass
    return ""


def _console_entrypoint(root: Path) -> Optional[Path]:
    """Locate a ``capt`` console script that actually drives *root*.

    A console script elsewhere on PATH may be bound to a different (possibly
    incomplete) installation, so it is only accepted when its interpreter
    resolves ``capt_cli`` from *root*.
    """
    candidate = shutil.which("capt")
    if not candidate:
        return None
    try:
        head = Path(candidate).read_text(encoding="utf-8", errors="replace").splitlines()
        if not head or not head[0].startswith("#!"):
            return None
        interp = head[0][2:].strip().split()[0]
    except Exception:
        return None
    if not interp or not os.access(interp, os.X_OK):
        return None
    try:
        out = subprocess.run(
            [interp, "-c", "import capt_cli,sys; sys.stdout.write(capt_cli.__file__)"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            cwd=str(root),
        )
    except Exception:
        return None
    if out.returncode != 0:
        return None
    resolved = Path(out.stdout.strip() or "/nonexistent").resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None
    return Path(candidate)


def _module_interpreter(root: Path) -> Optional[str]:
    """Pick an interpreter that can import capt_cli from *root* with cwd=root."""
    candidates: List[str] = [sys.executable]
    for name in ("python3", "python"):
        found = shutil.which(name)
        if found and found not in candidates:
            candidates.append(found)
    venv = root / ".venv" / "bin" / "python"
    if venv.is_file():
        candidates.insert(0, str(venv))
    for interp in candidates:
        if not interp or not os.access(interp, os.X_OK):
            continue
        try:
            out = subprocess.run(
                [interp, "-c", "import capt_cli"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
                cwd=str(root),
            )
        except Exception:
            continue
        if out.returncode == 0:
            return interp
    return None


def _agent_importable(root: Path, interp: str) -> bool:
    """The Agent Runner package must actually import, not merely exist on disk.

    The baseline for this mission proved the danger: a pip-installed capt_solo
    had the files but no ``capt_solo/agent`` at all. The inverse also bites — a
    tree whose ``capt_solo/agent/__init__.py`` raises on import would pass a
    file-existence check yet crash at boot. We verify the import for real.
    """
    try:
        out = subprocess.run(
            [interp, "-c", "import capt_solo.agent.runner"],
            capture_output=True, text=True, timeout=15, check=False, cwd=str(root),
        )
    except Exception:
        return False
    return out.returncode == 0


def resolve_capt_source(workspace: Path) -> Tuple[Optional[CaptSource], str]:
    """Resolve the canonical CAPT source for *workspace*.

    Returns ``(source, reason)``; ``source`` is ``None`` only when no tree
    containing the Agent Runner could be found. An incomplete tree is returned
    *with* ``missing_modules`` populated so the caller can report precisely what
    is absent rather than guessing.
    """
    workspace = workspace.resolve()
    candidates: List[Path] = []
    override = os.environ.get("CAPT_BRIDGE_SOURCE_ROOT")
    if override:
        # An explicit override is authoritative: if it is incomplete or
        # non-importable, the bridge must FAIL CLOSED rather than silently fall
        # through to another tree. Return it so the caller reports the defect.
        override_path = Path(override).expanduser().resolve()
        if (override_path / "capt_solo").is_dir() and (override_path / "capt_cli.py").is_file():
            missing = _missing_agent_modules(override_path)
            version = _read_version(override_path)
            if missing:
                return (
                    CaptSource(
                        root=override_path, launch_argv=(), launch_kind="none",
                        version=version, missing_modules=missing,
                        notes=(f"override {override_path} lacks the Agent Runner package",),
                    ),
                    f"override {override_path} lacks the Agent Runner package",
                )
            interp = _module_interpreter(override_path)
            if interp is None:
                return (
                    CaptSource(
                        root=override_path, launch_argv=(), launch_kind="none",
                        version=version,
                        notes=(f"override {override_path} has no interpreter that can import capt_cli",),
                    ),
                    f"override {override_path} has no usable interpreter",
                )
            if not _agent_importable(override_path, interp):
                return (
                    CaptSource(
                        root=override_path, launch_argv=(), launch_kind="none",
                        version=version, missing_modules=("capt_solo/agent (import fails)",),
                        notes=(f"override {override_path} has capt_solo/agent but it fails to import",),
                    ),
                    f"override {override_path} capt_solo/agent fails to import",
                )
            console = _console_entrypoint(override_path)
            if console is not None:
                return (
                    CaptSource(root=override_path, launch_argv=(str(console),), launch_kind="console_entrypoint", version=version),
                    "",
                )
            return (
                CaptSource(
                    root=override_path, launch_argv=(interp, str(override_path / "capt_cli.py")),
                    launch_kind="module_fallback", version=version,
                    notes=("console entrypoint absent or bound elsewhere; using module fallback",),
                ),
                "",
            )
        return None, f"override {override_path} is not a CAPT source tree (missing capt_solo/ or capt_cli.py)"
    candidates.append(workspace)
    for parent in workspace.parents:
        if (parent / "capt_solo").is_dir():
            candidates.append(parent)

    seen: set = set()
    incomplete: Optional[CaptSource] = None
    for root in candidates:
        key = str(root)
        if key in seen:
            continue
        seen.add(key)
        if not (root / "capt_solo").is_dir() or not (root / "capt_cli.py").is_file():
            continue
        missing = _missing_agent_modules(root)
        version = _read_version(root)
        if missing:
            if incomplete is None:
                incomplete = CaptSource(
                    root=root,
                    launch_argv=(),
                    launch_kind="none",
                    version=version,
                    missing_modules=missing,
                    notes=(
                        f"{root} imports as capt_solo {version or 'unknown'} but lacks "
                        "the Agent Runner package",
                    ),
                )
            continue

        console = _console_entrypoint(root)
        if console is not None:
            return (
                CaptSource(
                    root=root,
                    launch_argv=(str(console),),
                    launch_kind="console_entrypoint",
                    version=version,
                ),
                "",
            )
        interp = _module_interpreter(root)
        if interp is None:
            if incomplete is None:
                incomplete = CaptSource(
                    root=root,
                    launch_argv=(),
                    launch_kind="none",
                    version=version,
                    notes=(f"{root} has the Agent Runner but no interpreter can import capt_cli",),
                )
            continue
        # The Agent Runner package must import, not merely exist on disk.
        if not _agent_importable(root, interp):
            if incomplete is None:
                incomplete = CaptSource(
                    root=root,
                    launch_argv=(),
                    launch_kind="none",
                    version=version,
                    missing_modules=("capt_solo/agent (import fails)",),
                    notes=(f"{root} has capt_solo/agent but it fails to import",),
                )
            continue
        return (
            CaptSource(
                root=root,
                launch_argv=(interp, str(root / "capt_cli.py")),
                launch_kind="module_fallback",
                version=version,
                notes=("console entrypoint absent or bound elsewhere; using module fallback",),
            ),
            "",
        )

    if incomplete is not None:
        return incomplete, "; ".join(incomplete.notes)
    return None, "no CAPT source tree containing capt_solo/ and capt_cli.py was found"


def runner_env(nonce: str, socket_path: str, *, extra: Optional[dict] = None) -> dict:
    """Build the runner environment.

    The full parent environment is **not** inherited. The launch nonce is passed
    here — never in argv, where ``ps`` would expose it.
    """
    env = {k: os.environ[k] for k in _ENV_ALLOWLIST if k in os.environ}
    for k in _ENV_SECRET_ALLOWLIST:
        if k in os.environ:
            env[k] = os.environ[k]
    env["CAPT_BRIDGE_NONCE"] = nonce
    env["CAPT_BRIDGE_SOCKET"] = socket_path
    env["CAPT_BRIDGE_ACTIVE"] = "1"
    if extra:
        env.update({str(k): str(v) for k, v in extra.items()})
    return env


def redact_argv(argv: Sequence[str]) -> Tuple[str, ...]:
    """Argv for evidence. Asserts no secret value can appear in it."""
    secrets = {os.environ[k] for k in _ENV_SECRET_ALLOWLIST if os.environ.get(k)}
    secrets.discard("")
    out: List[str] = []
    for token in argv:
        redacted = token
        for secret in secrets:
            if secret and secret in redacted:
                redacted = redacted.replace(secret, "<redacted>")
        out.append(redacted)
    return tuple(out)
