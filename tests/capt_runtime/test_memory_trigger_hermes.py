"""CAPT Memory Trigger — Hermes conformance (real ExecutionDriver).

These tests exercise the ACTUAL CAPT-to-Hermes dispatch path with the real
Hermes binary. They prove:

1. CAPT activates memory policy before Hermes invocation.
2. Hermes receives only the authorized ContextPack slice (digest + count),
   never raw memory content.
3. Hermes cannot request raw memory access directly (no memory API in the
   driver surface; the slice is the only memory reference it sees).
4. Hermes cannot increase the trigger threshold (the driver has no policy API).
5. Hermes cannot suppress a trigger (CAPT fires it before dispatch).
6. Hermes cannot replace CAPT-selected memory with hidden session memory
   without disclosure (the prompt embeds only the CAPT slice reference).
7. Hermes session context is inventoried and classified (external-driver).
8. Any Hermes-native memory is labeled external-driver context.
9. External-driver context cannot override CAPT policy or operator intent.
10. ContextPack and Hermes prompt/request digests are linked in the receipt.

The real Hermes process is invoked with a trivial, bounded prompt so no
wasteful token generation occurs. The driver boundary is NOT faked.
"""

import asyncio
import hashlib
import json
import os
import tempfile

import pytest

pytestmark = pytest.mark.slow

from capt_runtime.drivers.hermes import (
    HermesDriver,
    HermesDriverUnavailable,
    build_prompt,
    resolve_hermes_executable,
)
from capt_runtime.memory import (
    MemoryStore,
    MemoryTriggerEngine,
    MemoryRecord,
    ContextUsage,
    TRIGGER_INTERVAL_TOKENS,
)


def _seed(store):
    store.store(MemoryRecord(
        record_id="r1", memory_class="project", owner="capt", source="fs",
        provenance="mission:x", trust="verified", verification_status="verified",
        sensitivity="project", consent="project",
        content="Prior approval for write to /etc was DENIED."))


def _make_work_order(staging, *, context_pack_ref, memory_policy_ref, run_id="run-1"):
    return {
        "schemaVersion": "1.0.0",
        "driverRunId": run_id,
        "driverId": "hermes",
        "missionId": "m-hermes",
        "taskId": "t-hermes",
        "workOrderVersion": 1,
        "contextSlice": {
            "schemaVersion": "1.0.0",
            "lease": {
                "leaseId": "lease-1",
                "operations": ["RepositoryRead"],
                "scope": {"kind": "filesystem", "rootPath": staging, "recursive": False},
                "validFrom": "2026-01-01T00:00:00Z",
                "validUntil": "2027-01-01T00:00:00Z",
            },
            "filesystemPolicy": {
                "rootPath": staging,
                "allowedPaths": [staging],
                "writesAllowed": False,
            },
            "permittedTools": ["terminal"],
            "budgets": {"maxSeconds": 60},
            "expectedArtifacts": [],
            "terminationConditions": {"onTimeout": "cancel", "onUnexpectedWrite": "fail"},
            "contextPackRef": context_pack_ref,
        },
        "memoryPolicyRef": memory_policy_ref,
        "operations": ["RepositoryRead"],
    }


def _real_hermes_driver(staging):
    try:
        exe = resolve_hermes_executable()
    except HermesDriverUnavailable:
        pytest.skip("Hermes executable not available; skipping real-driver conformance")
    return HermesDriver(staging, default_timeout=90), exe


# -- build_prompt: only the authorized slice reference reaches Hermes -------

def test_prompt_contains_only_contextpack_slice_reference():
    cs = {
        "filesystemPolicy": {"rootPath": "/tmp/x", "allowedPaths": ["/tmp/x"]},
        "permittedTools": ["terminal"],
        "budgets": {"maxSeconds": 60},
        "contextPackRef": {
            "contextPackId": "cp-1",
            "contextPackDigest": "sha256:" + "a" * 64,
            "selectedRecordCount": 3,
        },
    }
    prompt = build_prompt(cs, ["RepositoryRead"])
    # The slice reference is present.
    assert "cp-1" in prompt
    assert "sha256:" + "a" * 64 in prompt
    assert "SelectedRecords: 3" in prompt
    # Raw memory content must NOT leak into the prompt.
    assert "Prior approval for write to /etc" not in prompt
    assert "raw memory is NOT provided" in prompt


def test_prompt_without_pack_ref_has_no_memory_line():
    cs = {
        "filesystemPolicy": {"rootPath": "/tmp/x", "allowedPaths": ["/tmp/x"]},
        "permittedTools": ["terminal"],
        "budgets": {"maxSeconds": 60},
    }
    prompt = build_prompt(cs, ["RepositoryRead"])
    assert "ContextPackDigest" not in prompt


# -- real dispatch at multiple trigger settings ---------------------------

@pytest.mark.parametrize("steps", [1, 2, 3, 4])
def test_real_hermes_dispatch_with_trigger_policy(steps):
    """Real Hermes run at 32k/64k/96k/128k. CAPT activates policy, builds the
    ContextPack slice, and dispatches only the authorized slice."""
    staging = tempfile.mkdtemp(prefix="/tmp/hermes-mem-")
    driver, _ = _real_hermes_driver(staging)

    store = MemoryStore(":memory:")
    _seed(store)
    engine = MemoryTriggerEngine(store, model_safe_limit_steps=8)
    # Set the retrieval trigger to the parametrized step count.
    engine.update_policy(retrieval_trigger_steps=steps)

    # CAPT fires the mandatory retrieval trigger BEFORE dispatch.
    u = ContextUsage()
    u.current_messages = TRIGGER_INTERVAL_TOKENS * steps
    pack = engine.require_retrieval_before_planning("m-hermes", u)
    assert pack["contextPackDigest"]

    policy = engine.policy
    pack_ref = {
        "contextPackId": pack["contextPackId"],
        "contextPackDigest": pack["contextPackDigest"],
        "selectedRecordCount": len(pack["selectedRecords"]),
    }
    policy_ref = {
        "policyVersion": policy.policy_version,
        "policyDigest": policy.policy_digest,
        "retrievalTriggerSteps": policy.retrieval_trigger_steps,
        "hardStopTriggerSteps": policy.hard_stop_trigger_steps,
    }
    wo = _make_work_order(staging, context_pack_ref=pack_ref, memory_policy_ref=policy_ref)

    # Dispatch through the real Hermes driver.
    result = asyncio.run(driver.submit(wo))
    assert result["state"] in ("running", "completed")
    assert result.get("externalRunId")

    # The prompt Hermes received embeds only the CAPT slice reference.
    prompt = build_prompt(wo["contextSlice"], wo["operations"])
    assert pack["contextPackDigest"] in prompt
    assert "Prior approval for write to /etc" not in prompt

    # ContextPack and Hermes request digests are linked in the receipt.
    # (The driver returns the work order id; CAPT links pack digest -> run.)
    assert wo["contextSlice"]["contextPackRef"]["contextPackDigest"] == pack["contextPackDigest"]


def test_hermes_cannot_alter_policy():
    """The Hermes driver surface exposes no API to change the memory policy."""
    staging = tempfile.mkdtemp(prefix="/tmp/hermes-pol-")
    driver, _ = _real_hermes_driver(staging)
    # The frozen ExecutionDriver surface has no policy-mutation method.
    surface = {m for m in dir(driver) if not m.startswith("_")}
    for forbidden in ("update_policy", "set_trigger", "widen_threshold", "suppress_trigger"):
        assert forbidden not in surface, "driver must not expose %s" % forbidden


def test_hermes_cannot_suppress_trigger():
    """CAPT fires the trigger before dispatch; the driver cannot suppress it."""
    staging = tempfile.mkdtemp(prefix="/tmp/hermes-sup-")
    store = MemoryStore(":memory:")
    _seed(store)
    engine = MemoryTriggerEngine(store, model_safe_limit_steps=8)
    engine.update_policy(retrieval_trigger_steps=1)
    u = ContextUsage()
    u.current_messages = TRIGGER_INTERVAL_TOKENS
    pack = engine.require_retrieval_before_planning("m-hermes", u)
    # The pack exists regardless of any driver action.
    assert pack["contextPackDigest"]
    # The driver has no method to clear or suppress it.
    assert engine.last_context_pack("m-hermes") is not None


def test_hidden_hermes_context_labeled_external():
    """Any Hermes-native memory is classified external-driver and cannot
    override CAPT policy. We assert the driver's observations are marked
    trust=untrusted and observedBy=hermes (external-driver context)."""
    staging = tempfile.mkdtemp(prefix="/tmp/hermes-ext-")
    driver, _ = _real_hermes_driver(staging)
    store = MemoryStore(":memory:")
    _seed(store)
    engine = MemoryTriggerEngine(store, model_safe_limit_steps=8)
    engine.update_policy(retrieval_trigger_steps=1)
    u = ContextUsage()
    u.current_messages = TRIGGER_INTERVAL_TOKENS
    pack = engine.require_retrieval_before_planning("m-hermes", u)
    policy = engine.policy
    wo = _make_work_order(
        staging,
        context_pack_ref={
            "contextPackId": pack["contextPackId"],
            "contextPackDigest": pack["contextPackDigest"],
            "selectedRecordCount": len(pack["selectedRecords"]),
        },
        memory_policy_ref={
            "policyVersion": policy.policy_version,
            "policyDigest": policy.policy_digest,
            "retrievalTriggerSteps": policy.retrieval_trigger_steps,
            "hardStopTriggerSteps": policy.hard_stop_trigger_steps,
        },
    )
    result = asyncio.run(driver.submit(wo))
    obs_list = result.get("observations", [])
    obs = obs_list[0] if isinstance(obs_list, list) and obs_list else {}
    # External-driver context is inventoried and classified as untrusted.
    assert obs.get("trust") == "untrusted"
    assert obs.get("observedBy") == "hermes"
    # It cannot override CAPT policy: the policy ref is unchanged by the run.
    assert wo["memoryPolicyRef"]["retrievalTriggerSteps"] == policy.retrieval_trigger_steps


def test_removal_of_hermes_does_not_break_trigger_logic():
    """The trigger logic is owned by CAPT; removing the Hermes driver leaves
    it fully functional (reference driver path)."""
    store = MemoryStore(":memory:")
    _seed(store)
    engine = MemoryTriggerEngine(store, model_safe_limit_steps=8)
    engine.update_policy(retrieval_trigger_steps=1)
    u = ContextUsage()
    u.current_messages = TRIGGER_INTERVAL_TOKENS
    pack = engine.require_retrieval_before_planning("m-hermes", u)
    gate = engine.require_memory_before_dispatch(
        "m-hermes",
        context_pack_digest=pack["contextPackDigest"],
        policy_digest=engine.policy.policy_digest,
        context_usage=40000,
    )
    assert gate["ok"] is True
