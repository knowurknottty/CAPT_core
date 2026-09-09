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
