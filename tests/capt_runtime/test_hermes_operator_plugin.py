from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "integrations" / "hermes" / "capt-operator"
SOURCE = PLUGIN / "__init__.py"
MANIFEST = PLUGIN / "plugin.yaml"
INSTALLER = ROOT / "scripts" / "install_hermes_capt_operator.py"


def _load_plugin(name: str = "capt_operator_test"):
    spec = importlib.util.spec_from_file_location(name, SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_core_state_root_ignores_legacy_solo_home(monkeypatch, tmp_path: Path) -> None:
    core = tmp_path / "core-state"
    solo = tmp_path / "solo-state"
    monkeypatch.setenv("CAPT_STATE_DIR", str(core))
    monkeypatch.setenv("CAPT_SOLO_HOME", str(solo))
    module = _load_plugin("capt_operator_state_root")
    assert module._capt_home() == core
    assert module.CAPT_HOME == core
    assert module.CAPT_HOME != solo


def test_default_state_root_is_capt_not_capt_solo(monkeypatch) -> None:
    monkeypatch.delenv("CAPT_STATE_DIR", raising=False)
    monkeypatch.setenv("CAPT_SOLO_HOME", "/tmp/must-not-win")
    module = _load_plugin("capt_operator_default_root")
    assert module._capt_home() == Path.home() / ".capt"


def test_plugin_has_no_second_authority_import_or_direct_ledger_access() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert not re.search(r"(?:from|import)\s+capt_solo(?:\.|\s|$)", source)
    assert "CAPTRuntime" not in source
    assert "sqlite3" not in source
    assert "EventStore(" not in source
    assert "runtime.db" not in source
    assert "runtime.sock" in source


def test_manifest_declares_every_registered_tool_and_hook() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    registered_tools = set(re.findall(r'ctx\.register_tool\(\s*name="([^"]+)"', source))
    registered_hooks = set(re.findall(r'ctx\.register_hook\("([^"]+)"', source))
    assert set(manifest["provides_tools"]) == registered_tools
    assert set(manifest["provides_hooks"]) == registered_hooks
    assert registered_tools == {"capt_mode", "capt_ledger", "capt_govern"}


def test_installer_copies_canonical_plugin_bytes(tmp_path: Path) -> None:
    target = tmp_path / "capt-operator"
    proc = subprocess.run(
        [sys.executable, str(INSTALLER), "--target", str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    for name in ("__init__.py", "plugin.yaml", "README.md"):
        assert (target / name).read_bytes() == (PLUGIN / name).read_bytes()
