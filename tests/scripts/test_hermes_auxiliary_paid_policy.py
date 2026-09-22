import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ensure_hermes_auxiliary_paid_policy.py"
SPEC = importlib.util.spec_from_file_location("hermes_paid_policy", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


CONFIG = """auxiliary:
  free_only: true
  openrouter_model: nvidia/nemotron-3-ultra-550b-a55b:free
  goal_judge:
    provider: opencode-zen
    model: big-pickle
  moa_reference:
    timeout: 21600
    allow_paid: true
  moa_aggregator:
    timeout: 21600
moa:
  presets: {}
"""

def test_patch_config_enables_global_paid_auxiliary_and_preserves_other_fields():
    patched = MODULE.patch_config(CONFIG)
    assert "free_only: false" in patched
    assert "openrouter_model: nvidia/nemotron-3-ultra-550b-a55b:free" in patched
    assert "allow_paid: true" in patched
    assert MODULE.config_allows_paid_auxiliary(patched)


def test_patch_config_is_idempotent():
    once = MODULE.patch_config(CONFIG)
    twice = MODULE.patch_config(once)
    assert once == twice


def test_apply_writes_backup_and_conformant_state(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text(CONFIG)
    backups = tmp_path / "backups"

    result = MODULE.apply(config, backups)

    assert result["conformant"] is True
    assert result["paidAuxiliaryEnabled"] is True
    assert list(backups.glob("config.*.bak"))
    assert "free_only: false" in config.read_text()

