from __future__ import annotations

import pytest

from capt_solo.meta_foundry import DomainRegistry, MetaFoundry, MetaFoundryError
from capt_solo.meta_foundry.character_genesis import (
    COMPILER_ID,
    DOMAIN_ID,
    register,
)


def _foundry() -> MetaFoundry:
    registry = DomainRegistry()
    register(registry)
    return MetaFoundry(registry)


def _compile(character: dict):
    foundry = _foundry()
    intent = foundry.create_intent(
        domain_id=DOMAIN_ID,
        objective="Create a persistent hero for a children's video series",
        audience={"age_min": 5, "age_max": 9},
        preferences={
            "renderer_targets": ["seedance", "book-illustration"],
            "character": character,
        },
    )
    specification = foundry.specify(intent.intent_id)
    return foundry.compile(specification.specification_id, COMPILER_ID)


def test_character_package_is_compiled_not_rendered() -> None:
    artifact = _compile(
        {
            "identity": {"name": "Nova", "role": "hero"},
            "constitution": {"rules": ["Protect younger friends"]},
        }
    )
    assert artifact.payload["render_state"] == "compiled_not_rendered"
    assert artifact.payload["renderer_adapters"]["execution"] == "external"
    assert artifact.payload["renderer_adapters"]["visual_validation"]["state"] == "not_run"


def test_character_constitution_preserves_creator_control_and_child_safety() -> None:
    artifact = _compile({"identity": {"name": "Nova", "role": "hero"}})
    constitution = artifact.payload["character"]["constitution"]
    assert constitution["creator_control"] is True
    assert constitution["child_safety"] is True
    assert constitution["human_approval_required_for_canon_changes"] is True
    assert constitution["no_unapproved_identity_drift"] is True


def test_character_continuity_is_explicit_and_rejects_unapproved_drift() -> None:
    artifact = _compile(
        {
            "identity": {"name": "Nova", "role": "hero"},
            "immutable_traits": ["violet eyes", "star-shaped backpack"],
        }
    )
    continuity = artifact.payload["character"]["continuity"]
    assert continuity["immutable_traits"] == ["violet eyes", "star-shaped backpack"]
    assert continuity["drift_policy"] == "reject_unapproved"
    assert continuity["regression_tests_required"] is True


def test_character_emotion_defaults_are_bounded_and_complete() -> None:
    artifact = _compile({"identity": {"name": "Nova", "role": "hero"}})
    emotion = artifact.payload["character"]["emotion"]
    assert set(emotion) == {
        "joy",
        "curiosity",
        "trust",
        "fear",
        "calm",
        "energy",
        "empathy",
        "confidence",
        "wonder",
        "playfulness",
    }
    assert all(value == 0.5 for value in emotion.values())


def test_character_emotion_rejects_out_of_range_values() -> None:
    with pytest.raises(MetaFoundryError, match="emotion.joy must be between 0 and 1"):
        _compile(
            {
                "identity": {"name": "Nova", "role": "hero"},
                "emotion": {"joy": 1.2},
            }
        )


def test_character_memory_is_persistent_and_renderer_independent() -> None:
    artifact = _compile(
        {
            "identity": {"name": "Nova", "role": "hero"},
            "memory": {
                "episodic": [{"event": "Met Pip", "importance": 0.9}],
                "semantic": ["Pip is her younger friend"],
            },
        }
    )
    memory = artifact.payload["character"]["memory"]
    assert memory["persistent"] is True
    assert memory["retrieval_policy"] == "canon_relevant_first"
    assert memory["episodic"][0]["event"] == "Met Pip"
    assert artifact.payload["renderer_adapters"]["targets"] == [
        "seedance",
        "book-illustration",
    ]


def test_character_package_hash_is_deterministic_for_same_canonical_input() -> None:
    character = {
        "identity": {"name": "Nova", "role": "hero"},
        "visual": {"palette": ["violet", "gold"]},
        "immutable_traits": ["violet eyes"],
    }
    first = _compile(character)
    second = _compile(character)
    assert first.content_hash == second.content_hash


def test_character_behavior_tests_are_specified_but_not_falsely_reported_as_run() -> None:
    artifact = _compile(
        {
            "identity": {"name": "Nova", "role": "hero"},
            "behavior_tests": [
                {
                    "given": "scared",
                    "expect": "protects younger friend without bullying",
                }
            ],
        }
    )
    tests = artifact.payload["behavior_tests"]
    assert tests["state"] == "specified_not_run"
    assert len(tests["cases"]) == 1
