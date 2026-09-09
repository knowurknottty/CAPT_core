from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.slow
def test_runtime_installer_scrubs_python_import_overrides(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    script = repo / "capt_ui/surfaces/desktop_swift/script/install_local_runtime.sh"
    real_python = shutil.which("python3")
    assert real_python is not None

    wrapper_dir = tmp_path / "bin"
    wrapper_dir.mkdir()
    wrapper = wrapper_dir / "python3"
    wrapper.write_text(
        "#!/bin/zsh\n"
        "if [[ -n \"${PYTHONPATH:-}\" || -n \"${PYTHONHOME:-}\" ]]; then exit 91; fi\n"
        "exec \"$CAPT_TEST_REAL_PYTHON\" \"$@\"\n"
    )
    wrapper.chmod(0o755)

    env = dict(os.environ)
    env.update(
        {
            "PATH": str(wrapper_dir) + os.pathsep + env.get("PATH", ""),
            "CAPT_TEST_REAL_PYTHON": real_python,
            "CAPT_STATE_DIR": str(tmp_path / "state"),
            "PYTHONPATH": "/tmp/stale-capt-core",
            "PYTHONHOME": "/tmp/stale-python-home",
        }
    )
    completed = subprocess.run(
        [str(script)],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    runtime = tmp_path / "state/runtime-venv"
    assert (runtime / "bin/capt").is_file()
    assert (runtime / "CAPT_SOURCE_HEAD").read_text().strip()
    assert (runtime / "CAPT_WHEEL_SHA256").read_text().strip()
