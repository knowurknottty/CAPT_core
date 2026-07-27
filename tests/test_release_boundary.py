"""Tests for public/private boundary enforcement (M6) and engine security (M7).

Covers: no private modules in tree or wheel; PULSE disabled-by-default with no
network on import and fails-closed; engine input/exponent bounds; hostile payload
inertness (math engine); schema/workspace boundary already covered elsewhere.
"""
import ast
import os
import zipfile

import pytest

from capt_solo.engines.mathematics import MathematicsEngine, MathError
from capt_solo.pulse import PulseGateway, PulseDisabled, PulseError, default_gateway

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(_REPO, "capt_solo")
_PRIVATE_MARKERS = ["rys", "puter", "mesh", "ouroboros_private"]


def test_no_private_module_files():
    for root, _dirs, files in os.walk(_SRC):
        if "__pycache__" in root:
            continue
        for f in files:
            low = f.lower()
            assert not any(m in low for m in _PRIVATE_MARKERS), f"private file: {f}"


def test_no_private_imports_ast():
    for root, _dirs, files in os.walk(_SRC):
        if "__pycache__" in root:
            continue
        for f in files:
            if not f.endswith(".py"):
                continue
            tree = ast.parse(open(os.path.join(root, f)).read())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert alias.name.split(".")[0].lower() not in _PRIVATE_MARKERS
                elif isinstance(node, ast.ImportFrom) and node.module:
                    assert node.module.split(".")[0].lower() not in _PRIVATE_MARKERS


def test_pulse_disabled_by_default_no_network_on_import():
    # Importing the module must not open a socket. We verify the default gateway
    # is disabled and that calling complete() without configure raises (no call).
    gw = default_gateway()
    assert gw.enabled is False
    with pytest.raises(PulseDisabled):
        gw.complete("hello")


def test_pulse_fails_closed_without_endpoint():
    gw = PulseGateway()
    with pytest.raises(PulseError):
        gw.configure(endpoint="")  # empty endpoint rejected


def test_pulse_enabled_requires_explicit_config():
    gw = PulseGateway()
    gw.configure(endpoint="https://example.invalid/pulse", enabled=True)
    assert gw.enabled is True
    # A real network call would be made here; we do not perform it in tests.
    # Instead assert the gateway is now enabled (configuration path works).
    assert gw._config.endpoint == "https://example.invalid/pulse"


def test_engine_input_length_bound():
    eng = MathematicsEngine()
    with pytest.raises(MathError):
        eng.evaluate("1+" * 30000)


def test_engine_exponent_bound():
    eng = MathematicsEngine()
    with pytest.raises(MathError):
        eng.evaluate("2 ^ 99999")


def test_hostile_payload_inert():
    eng = MathematicsEngine()
    sentinel = "/tmp/capt_pulse_sentinel"
    if os.path.exists(sentinel):
        os.remove(sentinel)
    for payload in ["__import__('os').system('touch " + sentinel + "')",
                    "eval('1+1')", "open('/tmp/x')", "(lambda: 1)()"]:
        with pytest.raises(MathError):
            eng.evaluate(payload)
    assert not os.path.exists(sentinel)
    if os.path.exists(sentinel):
        os.remove(sentinel)


def test_wheel_excludes_private(tmp_path):
    dist = os.path.join(_REPO, "dist")
    wheels = []
    if os.path.isdir(dist):
        wheels = [os.path.join(dist, f) for f in os.listdir(dist) if f.endswith(".whl")]
    if not wheels:
        pytest.skip("no wheel built; run `python3 -m build --wheel` to inspect")
    z = zipfile.ZipFile(wheels[0])
    for name in z.namelist():
        low = name.lower()
        assert not any(m in low for m in _PRIVATE_MARKERS), f"private in wheel: {name}"
