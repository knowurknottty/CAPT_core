"""Memory trigger precedence must survive lower-authority update chains."""
import pytest

from capt_runtime.memory.policy import MemoryTriggerPolicy, PolicySource
from capt_runtime.memory.engine import MemoryTriggerEngine
from capt_runtime.memory.store import MemoryStore


def initial():
    return MemoryTriggerPolicy(
        retrieval_trigger_steps=2,
        compression_trigger_steps=2,
        checkpoint_trigger_steps=2,
        consolidation_trigger_steps=2,
        hard_stop_trigger_steps=2,
        model_safe_limit_steps=2,
        source=PolicySource.RUNTIME_POLICY,
    )


def test_lower_authority_never_overwrites_inherited_source():
    narrowed = initial().with_update(
        retrieval_trigger_steps=1,
        source=PolicySource.DRIVER_PREFERENCE,
        command_id="cmd-narrow",
    )
    assert narrowed.retrieval_trigger_steps == 1
    assert narrowed.source == PolicySource.RUNTIME_POLICY
    assert narrowed.previous_policy_digest == initial().policy_digest
    assert narrowed.command_id == "cmd-narrow"
    with pytest.raises(ValueError, match="may not widen"):
        narrowed.with_update(retrieval_trigger_steps=2,
                             source=PolicySource.DRIVER_PREFERENCE)


def test_model_ceiling_widened_directly_is_refused():
    with pytest.raises(ValueError, match="model_safe_limit_steps"):
        initial().with_update(model_safe_limit_steps=8,
                              source=PolicySource.DRIVER_PREFERENCE)


def test_two_step_safe_limit_escalation_refused_with_roundtrip():
    p = initial().with_update(retrieval_trigger_steps=1, source=PolicySource.DRIVER_PREFERENCE)
    roundtrip = MemoryTriggerPolicy.from_dict(p.to_dict())
    assert roundtrip.source == PolicySource.RUNTIME_POLICY
    with pytest.raises(ValueError, match="model_safe_limit_steps"):
        roundtrip.with_update(model_safe_limit_steps=8,
                              source=PolicySource.DRIVER_PREFERENCE)


def test_safe_limit_zero_rejected_even_after_valid_initial_policy():
    with pytest.raises(ValueError, match="model_safe_limit_steps"):
        initial().with_update(model_safe_limit_steps=0,
                              source=PolicySource.DRIVER_PREFERENCE)


def test_higher_authority_can_explicitly_change_ceiling():
    p = initial().with_update(
        hard_stop_trigger_steps=3,
        model_safe_limit_steps=3,
        source=PolicySource.CONSTITUTIONAL,
    )
    assert p.model_safe_limit_steps == 3
    assert p.source == PolicySource.CONSTITUTIONAL
    assert p.hard_stop_trigger_steps == 3


def test_engine_updates_preserve_runtime_source(tmp_path):
    engine = MemoryTriggerEngine(MemoryStore(":memory:"), model_safe_limit_steps=2,
                                 policy=initial())
    a = engine.update_policy(retrieval_trigger_steps=1,
                             source=PolicySource.DRIVER_PREFERENCE)
    assert a.source == PolicySource.RUNTIME_POLICY
    with pytest.raises(ValueError,match="may not widen"):
        engine.update_policy(model_safe_limit_steps=8,
                             source=PolicySource.DRIVER_PREFERENCE)
    assert engine.policy.policy_digest==a.policy_digest
