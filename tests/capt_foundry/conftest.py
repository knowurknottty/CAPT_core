"""Pytest configuration for the CAPT Foundry suite.

Mirrors tests/capt_runtime/conftest.py so the suite runs regardless of how
pytest is invoked.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GEN_PY = REPO / "contracts" / "generated" / "python"

for p in (str(REPO), str(GEN_PY)):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest

from capt_foundry import (
    AliasRegistry,
    CorpusRegistry,
    EntityRegistry,
    FoundryStore,
)
from capt_foundry.publisher import ArtifactPublisher
from capt_foundry.seal_export import SealAssetExporter


def fixed_clock(stamp: str = "2026-08-03T00:00:00Z"):
    """Deterministic clock so digests are reproducible across runs."""
    return lambda: stamp


@pytest.fixture()
def store():
    s = FoundryStore(":memory:")
    yield s
    s.close()


@pytest.fixture()
def entities(store):
    return EntityRegistry(store, clock=fixed_clock())


@pytest.fixture()
def aliases(store, entities):
    return AliasRegistry(store, entities, clock=fixed_clock())


@pytest.fixture()
def corpora(store):
    return CorpusRegistry(store, clock=fixed_clock())


@pytest.fixture()
def publisher(store, entities, aliases, corpora):
    return ArtifactPublisher(store, entities, aliases, corpora, clock=fixed_clock())


@pytest.fixture()
def exporter(entities, aliases, corpora):
    return SealAssetExporter(entities, aliases, corpora, clock=fixed_clock())
