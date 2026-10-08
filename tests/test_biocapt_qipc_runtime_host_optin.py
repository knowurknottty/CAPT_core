"""CAPT host's explicit, default-off bioCAPT QIPC registration gate.

These tests use canonical create_runtime() with temporary EventStore and the
already reviewed QIPC library. No production ledger/authorization is accessed.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from capt_runtime.composition import create_runtime
from desktop.capt_runtime_service import _register_optional_biocapt_qipc

SOURCE = Path.home() / "2clean4u/bioCAPT"
INTERPRETER = SOURCE / ".venv/bin/python"


def test_default_disabled_preserves_exact_legacy_registry(tmp_path):
    composition = create_runtime(str(tmp_path / "runtime.db"))
    try:
        before = composition.tool_registry.list_descriptors()
        _register_optional_biocapt_qipc(
            composition, enabled=False, source_root=None, interpreter=None
        )
        assert composition.tool_registry.list_descriptors() == before
        assert not composition.store.read_events()
    finally:
        composition.close()


@pytest.mark.parametrize("source,python", [
    ("/tmp/unexpected", None),
    (None, "/tmp/unexpected"),
    ("/tmp/unexpected", "/tmp/unexpected"),
])
def test_paths_without_explicit_enable_refused(tmp_path, source, python):
    composition = create_runtime(str(tmp_path / "runtime.db"))
    try:
        before = composition.tool_registry.list_descriptors()
        with pytest.raises(ValueError, match="EXPLICIT_ENABLE"):
            _register_optional_biocapt_qipc(
                composition, enabled=False,
                source_root=source, interpreter=python,
            )
        assert composition.tool_registry.list_descriptors() == before
        assert not composition.store.read_events()
    finally:
        composition.close()


@pytest.mark.parametrize("source,python", [
    (None, None),
    ("/tmp/nonexistent", None),
    (None, "/tmp/nonexistent"),
])
def test_explicit_enable_requires_both_paths(tmp_path, source, python):
    composition = create_runtime(str(tmp_path / "runtime.db"))
    try:
        before = composition.tool_registry.list_descriptors()
        with pytest.raises(ValueError, match="EXPLICIT_SOURCE_AND_INTERPRETER"):
            _register_optional_biocapt_qipc(
                composition, enabled=True,
                source_root=source, interpreter=python,
            )
        assert composition.tool_registry.list_descriptors() == before
        assert not composition.store.read_events()
    finally:
        composition.close()


def test_real_reviewed_source_attaches_without_creating_authority(tmp_path):
    if not (SOURCE / "modules/qipc_mobile.py").exists() or not INTERPRETER.exists():
        pytest.skip("requires real local bioCAPT source")
    try:
        from capt_ouroboros.qipc_tool_broker import REVIEWED_QIPC_SHA256
    except ImportError:
        pytest.skip("optional reviewed Ouroboros package not installed")
    import hashlib

    if hashlib.sha256(
        (SOURCE / "modules/qipc_mobile.py").read_bytes()
    ).hexdigest() != REVIEWED_QIPC_SHA256:
        pytest.skip("source drift is tested separately in adapter tests")
    composition = create_runtime(str(tmp_path / "runtime.db"))
    try:
        _register_optional_biocapt_qipc(
            composition, enabled=True,
            source_root=str(SOURCE), interpreter=str(INTERPRETER),
        )
        registered = composition.tool_registry.require("biocapt.qipc")
        assert registered["descriptor"]["operations"] == ["biocapt.qipc.compute"]
        assert registered["adapter"].calls == 0
        assert composition.tool_registry.readiness("biocapt.qipc")["status"] == "available"
        assert not composition.store.read_events()
    finally:
        composition.close()
