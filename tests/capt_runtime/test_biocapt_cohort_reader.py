"""CAPT bioCAPT reader permission and configuration tests."""
import pytest
from capt_runtime.biocapt_cohort_reader import BioCAPTLocalCohortReader
from capt_runtime.store import EventStore
from capt_runtime.errors import CapabilityDenied


def test_requires_persisted_capability():
    reader = BioCAPTLocalCohortReader(EventStore(":memory:"), "/tmp/not-present.sock")
    with pytest.raises(CapabilityDenied):
        reader.observe(grant_id="unknown", lease_id="unknown",
                       mission_id="m", task_id="t", actor_id="operator")


def test_age_budget_is_bounded():
    with pytest.raises(ValueError):
        BioCAPTLocalCohortReader(EventStore(":memory:"), "/tmp/not-present.sock",
                                 max_age_seconds=121)
