"""doctor.sh must not interpolate environment variables into Python source.

Regression coverage for the recovered security candidate
`command-injection:doctor.sh:97`, in which `$HERMES_CONFIG_DIR` was embedded
directly inside a single-quoted Python string literal passed to `python3 -c`.
A crafted environment value could close the literal and execute arbitrary
Python with the invoking user's privileges.

The fix passes filesystem paths as `sys.argv` arguments instead of splicing
them into program text. These tests assert both the structural property (no
shell variable appears inside a `python3 -c` program) and the behavioural
property (a malicious value is treated as literal data).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCTOR_SH = REPO_ROOT / "doctor.sh"

# A payload that would execute if spliced into Python source, but is inert
# when received as an ordinary argv string.
INJECTION_PAYLOAD = (
    "' + (__import__(\"builtins\").print(\"CAPT_INJECTION\") or \"\") + '"
)


@pytest.mark.skipif(not DOCTOR_SH.exists(), reason="doctor.sh not present")
def test_doctor_sh_does_not_interpolate_shell_vars_into_python_source():
    """No `python3 -c` program text may contain a shell variable expansion."""
    script = DOCTOR_SH.read_text()
    offenders = []
    for program in re.findall(r'python3\s+-c\s+"([^"]*)"', script):
        if re.search(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?", program):
            offenders.append(program)
    assert not offenders, (
        "shell variables interpolated into python -c source (command injection): "
        + "; ".join(offenders)
    )


@pytest.mark.skipif(not DOCTOR_SH.exists(), reason="doctor.sh not present")
def test_doctor_sh_plugin_check_uses_argv():
    """The plugin.json check must read its path from sys.argv, not program text."""
    script = DOCTOR_SH.read_text()
    assert "sys.argv[1]" in script, "plugin manifest path must be passed via argv"
    assert "open('$HERMES_CONFIG_DIR" not in script
    assert "$HERMES_CONFIG_DIR/plugins/capt-solo/plugin.json\"" in script, (
        "path should be supplied as a quoted shell argument"
    )


@pytest.mark.skipif(not DOCTOR_SH.exists(), reason="doctor.sh not present")
def test_doctor_sh_is_syntactically_valid():
    result = subprocess.run(
        ["bash", "-n", str(DOCTOR_SH)], capture_output=True, text=True
    )
    assert result.returncode == 0, f"bash -n failed: {result.stderr}"


def test_argv_pattern_neutralizes_injection_payload():
    """Behavioural proof: the argv form treats the payload as literal data."""
    program = (
        "import json,sys; d=json.load(open(sys.argv[1])); "
        "sys.exit(0 if len(d.get('tools',[]))==46 else 1)"
    )
    result = subprocess.run(
        [sys.executable, "-c", program, f"{INJECTION_PAYLOAD}/plugins/x.json"],
        capture_output=True,
        text=True,
    )
    assert "CAPT_INJECTION" not in result.stdout, (
        "payload executed — argv form failed to contain the injection"
    )
    assert "FileNotFoundError" in result.stderr, (
        "expected the payload to be treated as a literal filesystem path"
    )


def test_interpolated_pattern_would_execute_payload():
    """Control: proves the ORIGINAL pattern was genuinely exploitable.

    This documents why the fix is required. If this ever stops executing the
    payload, the reproduction assumptions have changed and the regression
    guard above should be re-examined.
    """
    vulnerable_program = (
        "import json,sys; "
        f"d=json.load(open('{INJECTION_PAYLOAD}/plugins/capt-solo/plugin.json')); "
        "sys.exit(0 if len(d.get('tools',[]))==46 else 1)"
    )
    result = subprocess.run(
        [sys.executable, "-c", vulnerable_program], capture_output=True, text=True
    )
    assert "CAPT_INJECTION" in result.stdout, (
        "control case did not reproduce; injection semantics have changed"
    )
