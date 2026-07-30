"""Architecture CLI must degrade gracefully outside a repository checkout.

Regression coverage for the v0.5 release-hardening finding that
`capt architecture validate` raised an unhandled ModuleNotFoundError when run
from an installed distribution.

The `architecture` package is a repository-development tool (it validates
architecture/registry.yaml against docs/adr and the source tree layout) and is
deliberately excluded from the wheel and sdist. Installed users must therefore
receive a clear, actionable error rather than a traceback.
"""

from __future__ import annotations

import argparse
import builtins
import io
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import capt_cli  # noqa: E402


def _args(action: str = "validate") -> argparse.Namespace:
    return argparse.Namespace(group="architecture", action=action)


def test_architecture_validate_reports_clear_error_when_package_absent(monkeypatch):
    """Simulate an installed distribution where `architecture` is not importable."""
    real_import = builtins.__import__

    def _blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "architecture" or name.startswith("architecture."):
            raise ModuleNotFoundError(f"No module named {name!r}")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _blocked_import)

    buf = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(err):
        rc = capt_cli._cmd_architecture(_args("validate"), as_json=False)

    output = buf.getvalue() + err.getvalue()

    # Must fail cleanly, not raise.
    assert rc != 0, "architecture validate must report failure when unavailable"
    # Must explain the cause and the remedy.
    assert "repository checkout" in output, (
        f"error must direct the user to a source checkout; got: {output!r}"
    )
    assert "architecture" in output
    # Must NOT leak a raw traceback artifact.
    assert "Traceback" not in output
    assert "ModuleNotFoundError" not in output


def test_architecture_validate_raises_nothing_uncaught_when_package_absent(monkeypatch):
    """The failure path must never propagate ModuleNotFoundError to the caller."""
    real_import = builtins.__import__

    def _blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "architecture" or name.startswith("architecture."):
            raise ModuleNotFoundError(f"No module named {name!r}")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _blocked_import)

    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            capt_cli._cmd_architecture(_args("validate"), as_json=True)
    except ModuleNotFoundError as exc:  # pragma: no cover - regression guard
        pytest.fail(f"ModuleNotFoundError escaped the CLI boundary: {exc}")


def test_architecture_validate_succeeds_in_repository_checkout():
    """In a source checkout the command must still work (no regression)."""
    pytest.importorskip("architecture.validate_registry")

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = capt_cli._cmd_architecture(_args("validate"), as_json=True)

    assert rc == 0, f"architecture validate must pass in a checkout; output={buf.getvalue()!r}"
