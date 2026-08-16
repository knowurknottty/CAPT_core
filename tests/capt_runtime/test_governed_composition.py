from capt_runtime.governed_composition import (
    DependencyEpoch, TopologyAttestation, capability_world_digest, runtime_debt,
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


def test_capability_world_digest_is_deterministic_and_secret_free():
    one = {"provider": "ollama", "model": "m", "dependencies": {"context": 2, "tools": 1}, "api_key": "never-digest"}
    two = {"dependencies": {"tools": 1, "context": 2}, "model": "m", "provider": "ollama", "api_key": "different-secret"}
    assert capability_world_digest(one) == capability_world_digest(two)
    assert capability_world_digest(one) != capability_world_digest({"provider": "ollama", "model": "other", "dependencies": {"context": 2, "tools": 1}})


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
    assert runtime_debt(epoch=epoch, topology=topology, expected_resources=[])["runtimeDebt"] == 0
