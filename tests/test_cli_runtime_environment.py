from __future__ import annotations


def test_runtime_child_environment_scrubs_python_import_overrides() -> None:
    from capt_cli import _runtime_child_environment

    sanitized = _runtime_child_environment(
        {
            "PATH": "/usr/bin:/bin",
            "PYTHONPATH": "/tmp/stale-core",
            "PYTHONHOME": "/tmp/stale-python",
            "CAPT_LAB_STATE_DIR": "/tmp/labs",
        }
    )
    assert "PYTHONPATH" not in sanitized
    assert "PYTHONHOME" not in sanitized
    assert sanitized["PATH"] == "/usr/bin:/bin"
    assert sanitized["CAPT_LAB_STATE_DIR"] == "/tmp/labs"


def test_runtime_start_pins_source_checkout(tmp_path, monkeypatch):
    """Daemon must load the same source tree as the launching CAPT CLI."""
    import argparse
    from pathlib import Path
    import pytest
    import capt_cli

    options = {"state_dir":tmp_path, "sock":tmp_path/"runtime.sock",
               "ledger":tmp_path/"runtime.db", "token":tmp_path/"runtime.token",
               "pid":tmp_path/"runtime.pid"}
    observed = {}
    class Intercept(Exception):
        pass
    def reject_spawn(argv, **kwargs):
        observed.update({"argv":argv, **kwargs})
        raise Intercept
    monkeypatch.setattr(capt_cli.subprocess, "Popen", reject_spawn)
    with pytest.raises(Intercept):
        capt_cli._cmd_ramp_start(argparse.Namespace(seed=False), options, False)
    assert Path(observed["cwd"]).resolve() == Path(capt_cli.__file__).resolve().parent
    assert observed["argv"][1:3] == ["-m", "desktop.capt_runtime_service"]
    assert "PYTHONPATH" not in observed["env"]
