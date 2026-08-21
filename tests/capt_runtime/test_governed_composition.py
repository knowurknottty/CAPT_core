import pytest

from capt_runtime.governed_composition import (
    DependencyEpoch,
    TopologyAttestation,
    capability_world_digest,
    runtime_debt,
)


def test_stale_generation_completion_cannot_overwrite_current_activation():
    epoch = DependencyEpoch()
    first = epoch.generation
    second = epoch.advance()
    assert first != second
    assert epoch.activate(first) is False
    assert epoch.accepts_completion(first) is False
    assert epoch.activate(second) is True
    assert epoch.accepts_completion(second) is True


def test_capability_world_digest_is_deterministic_secret_free_and_binding_sensitive():
    one = {
        "provider": "openrouter",
        "model": "m",
        "dependencies": {"context": 2, "tools": 1},
        "api_key": "never-digest",
        "credential_ref": "env:OPENROUTER_API_KEY",
        "base_url": "https://user:pass@example.com/v1?token=abc",
    }
    two = {
        "dependencies": {"tools": 1, "context": 2},
        "model": "m",
        "provider": "openrouter",
        "api_key": "different-secret",
        "credential_ref": "env:OPENROUTER_API_KEY",
        "base_url": "https://other:secret@example.com/v1?token=xyz",
    }
    assert capability_world_digest(one) == capability_world_digest(two)
    assert capability_world_digest(one) != capability_world_digest(
        {**one, "credential_ref": "keychain:other-account"}
    )
    assert capability_world_digest(one) != capability_world_digest(
        {**one, "model": "other"}
    )


def test_topology_leak_fails_attestation_and_debt_reconciles_to_zero():
    topology = TopologyAttestation()
    before = topology.digest()
    topology.mount("provider-callback")
    assert not topology.attests_restored(before)
    epoch = DependencyEpoch()
    debt = runtime_debt(epoch=epoch, topology=topology, expected_resources=[])
    assert debt["runtimeDebt"] == 1
    assert debt["quiescent"] is False
    topology.unmount("provider-callback")
    assert topology.attests_restored(before)
    assert runtime_debt(
        epoch=epoch, topology=topology, expected_resources=[]
    )["runtimeDebt"] == 0


def test_unknown_unmount_is_visible_debt_not_silent_cleanup():
    topology = TopologyAttestation()
    with pytest.raises(ValueError, match="TOPOLOGY_RESOURCE_NOT_MOUNTED"):
        topology.unmount("ghost")
    debt = runtime_debt(
        epoch=DependencyEpoch(), topology=topology, expected_resources=[]
    )
    assert debt["runtimeDebt"] == 1
    assert debt["topologyAnomalies"] == ["unmount-missing:ghost"]
    assert debt["quiescent"] is False


def test_runtime_debt_distinguishes_missing_cleanup_and_compensation_obligations():
    topology = TopologyAttestation(resources={"mounted"})
    debt = runtime_debt(
        epoch=DependencyEpoch(state="RECONCILING"),
        topology=topology,
        expected_resources=["expected"],
        indeterminate_effects=1,
        failed_cleanups=1,
        pending_compensations=1,
    )
    assert debt["epochState"] == "RECONCILING"
    assert debt["unexpectedResources"] == ["mounted"]
    assert debt["missingExpectedResources"] == ["expected"]
    assert debt["indeterminateEffects"] == 1
    assert debt["failedCleanups"] == 1
    assert debt["pendingCompensations"] == 1
    assert debt["runtimeDebt"] == 6
    assert debt["quiescent"] is False
