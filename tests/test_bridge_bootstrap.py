"""Permanent tests for the CAPT Bootstrap Bridge.

Covers every failure mode named in the mission. These are tracked regression
tests, not ephemeral scripts.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from capt_solo.bridge.contracts import (
    BLOCK_CAPT_INCOMPLETE,
    BLOCK_DOCTOR_FAILED,
    BLOCK_MISSION_REQUIRED,
    BLOCK_READY_MALFORMED,
    BLOCK_READY_UNAUTHENTICATED,
    BLOCK_WORKSPACE_MISSING,
    BOOT_STATE_FULL,
    BOOT_STATE_PARTIAL,
    BOOT_STATE_SKILL_ONLY,
    BOOT_STATE_UNAVAILABLE,
    OWNER_CAPT_AFTER_READY,
    OWNER_HERMES_BEFORE_BRIDGE,
    OWNER_NONE_WHEN_BLOCKED,
    BridgeReadyEvent,
    BridgeResult,
    ProviderOwnership,
    ProviderOwnershipViolation,
    blocked,
)

REPO = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _valid_event(nonce: str = "n0nce", pid: int = 4242, mission: str = "m1") -> BridgeReadyEvent:
    ev = BridgeReadyEvent(
        run_id="agentrun-abc",
        mission_id=mission,
        session_id="sess-1",
        intent_id="intent-1",
        checkpoint_id="m1@phase",
        contextpack_digest="sha256:deadbeef",
        memory_use_decision_id="dec-1",
        memory_use_gate="PASS",
        ctp_transaction_id="tx-1",
        khsb_correlation_id="corr-1",
        provider_owner="CAPT_AGENT_RUNNER",
        execution_mode="GOVERNED",
        runner_pid=pid,
        bridge_nonce=nonce,
    )
    return ev.with_digest()


# ---------------------------------------------------------------------------
# skill discovery and digest
# ---------------------------------------------------------------------------
def test_skill_source_is_tracked_and_digestible():
    skill = REPO / "skills" / "hermes" / "capt-core-runtime" / "SKILL.md"
    assert skill.is_file(), "tracked skill source must exist in the repository"
    import hashlib

    digest = hashlib.sha256(skill.read_bytes()).hexdigest()
    assert len(digest) == 64


def test_missing_skill_source_is_detectable(tmp_path):
    assert not (tmp_path / "skills" / "hermes" / "capt-core-runtime").exists()


# ---------------------------------------------------------------------------
# CAPT source resolution: mixed checkout / incomplete install
# ---------------------------------------------------------------------------
def test_mixed_checkout_without_agent_package_is_rejected(tmp_path, monkeypatch):
    """A capt_solo that imports but has no Agent Runner must NOT be accepted.

    This is the exact real-world condition proved in the baseline: the installed
    0.5.0 site-packages copy has no capt_solo/agent/ at all.
    """
    from capt_solo.bridge.resolver import resolve_capt_source

    fake = tmp_path / "fake-capt"
    (fake / "capt_solo").mkdir(parents=True)
    (fake / "capt_solo" / "__init__.py").write_text('__version__ = "0.5.0"\n')
    (fake / "capt_cli.py").write_text("def main():\n    return 0\n")
    monkeypatch.setenv("CAPT_BRIDGE_SOURCE_ROOT", str(fake))

    source, reason = resolve_capt_source(fake)
    assert source is not None
    assert not source.complete
    assert "capt_solo/agent/runner.py" in source.missing_modules
    assert "Agent Runner" in reason


def test_incomplete_source_blocks_boot(tmp_path, monkeypatch):
    from capt_solo.bridge.boot_bridge import boot_bridge

    fake = tmp_path / "fake-capt"
    (fake / "capt_solo").mkdir(parents=True)
    (fake / "capt_solo" / "__init__.py").write_text('__version__ = "0.5.0"\n')
    (fake / "capt_cli.py").write_text("def main():\n    return 0\n")
    monkeypatch.setenv("CAPT_BRIDGE_SOURCE_ROOT", str(fake))

    result, handle = boot_bridge(workspace_path=str(fake), mission_id="m1")
    assert handle is None
    assert BLOCK_CAPT_INCOMPLETE in result.block_codes
    assert not result.provider_allowed


def test_canonical_source_resolves_with_launch_argv():
    from capt_solo.bridge.resolver import resolve_capt_source

    source, reason = resolve_capt_source(REPO)
    assert source is not None, reason
    assert source.complete, f"missing: {source.missing_modules}"
    assert source.launch_argv
    assert source.launch_kind in ("console_entrypoint", "module_fallback")


def test_module_fallback_used_when_console_entrypoint_absent(monkeypatch):
    """No `capt` on PATH -> canonical module fallback, not failure."""
    import capt_solo.bridge.resolver as resolver

    monkeypatch.setattr(resolver, "_console_entrypoint", lambda root: None)
    source, reason = resolver.resolve_capt_source(REPO)
    assert source is not None, reason
    assert source.launch_kind == "module_fallback"
    assert source.launch_argv[-1].endswith("capt_cli.py")


# ---------------------------------------------------------------------------
# explicit mission requirement / workspace
# ---------------------------------------------------------------------------
def test_mission_is_mandatory():
    from capt_solo.bridge.boot_bridge import boot_bridge

    result, handle = boot_bridge(workspace_path=str(REPO), mission_id="")
    assert BLOCK_MISSION_REQUIRED in result.block_codes
    assert handle is None
    assert result.provider_owner == OWNER_NONE_WHEN_BLOCKED


def test_missing_workspace_blocks(tmp_path):
    from capt_solo.bridge.boot_bridge import boot_bridge

    result, _ = boot_bridge(workspace_path=str(tmp_path / "nope"), mission_id="m1")
    assert BLOCK_WORKSPACE_MISSING in result.block_codes


def test_boot_state_is_skill_only_when_skill_present():
    """The precise defect classification is preserved."""
    from capt_solo.bridge.boot_bridge import boot_bridge

    result, _ = boot_bridge(workspace_path="/nonexistent", mission_id="m1", skill_present=True)
    assert result.boot_state == BOOT_STATE_SKILL_ONLY
    result2, _ = boot_bridge(workspace_path="/nonexistent", mission_id="m1", skill_present=False)
    assert result2.boot_state == BOOT_STATE_UNAVAILABLE


# ---------------------------------------------------------------------------
# doctor gate
# ---------------------------------------------------------------------------
def test_doctor_failure_blocks_boot(monkeypatch):
    import capt_solo.bridge.boot_bridge as bb

    monkeypatch.setattr(bb, "run_doctor", lambda source: (False, {}, "doctor says no"))
    result, handle = bb.boot_bridge(workspace_path=str(REPO), mission_id="m1")
    assert BLOCK_DOCTOR_FAILED in result.block_codes
    assert handle is None, "runner must not launch when the doctor gate fails"


def test_doctor_uses_toplevel_json_flag():
    """`capt agent doctor --json` is a CLI error; --json must be top-level."""
    from capt_solo.bridge.resolver import resolve_capt_source

    source, _ = resolve_capt_source(REPO)
    assert source is not None
    wrong = subprocess.run(
        [*source.launch_argv, "agent", "doctor", "--json"],
        capture_output=True, text=True, timeout=60, cwd=str(source.root),
    )
    assert wrong.returncode != 0
    assert "unrecognized arguments" in (wrong.stderr or "")

    right = subprocess.run(
        [*source.launch_argv, "--json", "agent", "doctor"],
        capture_output=True, text=True, timeout=60, cwd=str(source.root),
    )
    assert right.returncode == 0
    assert json.loads(right.stdout)["ok"] is True


# ---------------------------------------------------------------------------
# READY event validation
# ---------------------------------------------------------------------------
def test_valid_ready_event_passes():
    ev = _valid_event()
    ok, codes, reason = ev.validate(expected_nonce="n0nce", expected_mission_id="m1", expected_pid=4242)
    assert ok, f"{codes} {reason}"


def test_ready_event_wrong_nonce_rejected():
    ev = _valid_event(nonce="attacker")
    ok, codes, _ = ev.validate(expected_nonce="n0nce", expected_pid=4242)
    assert not ok
    assert BLOCK_READY_UNAUTHENTICATED in codes


def test_ready_event_without_nonce_rejected():
    ev = _valid_event()
    ev.bridge_nonce = ""
    ok, codes, _ = ev.validate(expected_nonce="n0nce", expected_pid=4242)
    assert not ok
    assert BLOCK_READY_UNAUTHENTICATED in codes


def test_ready_event_wrong_pid_rejected():
    ev = _valid_event(pid=1)
    ok, codes, _ = ev.validate(expected_nonce="n0nce", expected_pid=4242)
    assert not ok
    assert BLOCK_READY_UNAUTHENTICATED in codes


def test_ready_event_missing_field_rejected():
    ev = _valid_event()
    ev.ctp_transaction_id = ""
    ok, codes, reason = ev.validate(expected_nonce="n0nce", expected_pid=4242)
    assert not ok
    assert BLOCK_READY_MALFORMED in codes
    assert "ctp_transaction_id" in reason


def test_ready_event_tampered_digest_rejected():
    ev = _valid_event()
    ev.session_id = "hijacked"  # digest no longer matches
    ok, codes, _ = ev.validate(expected_nonce="n0nce", expected_pid=4242)
    assert not ok
    assert BLOCK_READY_MALFORMED in codes


def test_ready_event_gate_not_pass_rejected():
    ev = BridgeReadyEvent(
        run_id="r", mission_id="m1", session_id="s", intent_id="i", checkpoint_id="c",
        contextpack_digest="d", memory_use_decision_id="dd", memory_use_gate="BLOCKED",
        ctp_transaction_id="t", khsb_correlation_id="k",
        provider_owner="CAPT_AGENT_RUNNER", execution_mode="GOVERNED",
        runner_pid=7, bridge_nonce="n0nce",
    ).with_digest()
    ok, codes, _ = ev.validate(expected_nonce="n0nce", expected_pid=7)
    assert not ok
    assert "MEMORY_USE_GATE_NOT_PASSED" in codes


def test_forged_ready_text_from_model_output_is_not_accepted():
    """Model text claiming readiness must never validate."""
    forged = (
        "READY: provider_owner=CAPT_AGENT_RUNNER execution_mode=GOVERNED "
        "memory_use_gate=PASS mission_id=m1"
    )
    with pytest.raises(Exception):
        json.loads(forged)
    ev = BridgeReadyEvent.from_mapping({"run_id": forged})
    ok, codes, _ = ev.validate(expected_nonce="n0nce")
    assert not ok
    assert BLOCK_READY_UNAUTHENTICATED in codes


def test_hand_written_ready_json_without_nonce_rejected(tmp_path):
    """A manually written JSON file is not a READY event."""
    payload = {
        "run_id": "r", "mission_id": "m1", "session_id": "s", "intent_id": "i",
        "checkpoint_id": "c", "contextpack_digest": "d", "memory_use_decision_id": "dd",
        "memory_use_gate": "PASS", "ctp_transaction_id": "t", "khsb_correlation_id": "k",
        "provider_owner": "CAPT_AGENT_RUNNER", "execution_mode": "GOVERNED",
    }
    p = tmp_path / "ready.json"
    p.write_text(json.dumps(payload))
    ev = BridgeReadyEvent.from_mapping(json.loads(p.read_text()))
    ok, codes, _ = ev.validate(expected_nonce="real-nonce", expected_pid=99)
    assert not ok
    assert BLOCK_READY_UNAUTHENTICATED in codes


def test_ready_event_nonce_never_serialised():
    ev = _valid_event(nonce="s3cret-nonce")
    body = json.dumps(ev.redacted_dict())
    assert "s3cret-nonce" not in body
    assert "<redacted>" in body


# ---------------------------------------------------------------------------
# runner lifecycle
# ---------------------------------------------------------------------------
def test_runner_startup_timeout(tmp_path):
    """A runner that never emits READY times out and blocks."""
    from capt_solo.bridge.resolver import CaptSource
    from capt_solo.bridge.runner_process import launch_runner

    script = tmp_path / "sleeper.py"
    script.write_text("import time\ntime.sleep(60)\n")
    source = CaptSource(
        root=tmp_path, launch_argv=(sys.executable, str(script)), launch_kind="module_fallback"
    )
    handle = launch_runner(
        source, workspace=tmp_path, mission_id="m1", resume=True, timeout_s=2.0
    )
    assert not handle.ready
    assert "RUNNER_STARTUP_TIMEOUT" in handle.block_codes


def test_runner_death_before_ready_blocks(tmp_path):
    from capt_solo.bridge.resolver import CaptSource
    from capt_solo.bridge.runner_process import launch_runner

    script = tmp_path / "dier.py"
    script.write_text("import sys\nsys.exit(3)\n")
    source = CaptSource(
        root=tmp_path, launch_argv=(sys.executable, str(script)), launch_kind="module_fallback"
    )
    handle = launch_runner(source, workspace=tmp_path, mission_id="m1", resume=True, timeout_s=20.0)
    assert not handle.ready
    assert "RUNNER_DIED" in handle.block_codes


def test_duplicate_runner_prevented(tmp_path):
    from capt_solo.bridge.runner_process import DuplicateRunnerError, acquire_runner_lock

    lock = acquire_runner_lock(tmp_path, "m1")
    lock.write_text(json.dumps({"pid": os.getpid(), "pgid": os.getpid(), "mission_id": "m1"}))
    with pytest.raises(DuplicateRunnerError):
        acquire_runner_lock(tmp_path, "m1")


def test_stale_runner_lock_is_reclaimed(tmp_path):
    from capt_solo.bridge.runner_process import acquire_runner_lock

    lock = acquire_runner_lock(tmp_path, "m1")
    lock.write_text(json.dumps({"pid": 999_999_999, "mission_id": "m1"}))
    reclaimed = acquire_runner_lock(tmp_path, "m1")  # must not raise
    assert reclaimed == lock


def test_no_secrets_in_runner_argv(monkeypatch):
    from capt_solo.bridge.resolver import redact_argv

    monkeypatch.setenv("LM_STUDIO_API_KEY", "sk-super-secret-value")
    argv = redact_argv(("capt", "--token", "sk-super-secret-value"))
    assert "sk-super-secret-value" not in " ".join(argv)
    assert "<redacted>" in " ".join(argv)


def test_runner_env_is_not_full_parent_env(monkeypatch):
    from capt_solo.bridge.resolver import runner_env

    monkeypatch.setenv("SOME_UNRELATED_SECRET", "leak-me")
    env = runner_env("nonce", "/tmp/x.sock")
    assert "SOME_UNRELATED_SECRET" not in env
    assert env["CAPT_BRIDGE_NONCE"] == "nonce"


def test_nonce_travels_in_env_not_argv(tmp_path):
    """`ps` must never expose the launch nonce."""
    from capt_solo.bridge.resolver import CaptSource
    from capt_solo.bridge.runner_process import launch_runner

    script = tmp_path / "dier.py"
    script.write_text("import sys\nsys.exit(1)\n")
    source = CaptSource(
        root=tmp_path, launch_argv=(sys.executable, str(script)), launch_kind="module_fallback"
    )
    handle = launch_runner(source, workspace=tmp_path, mission_id="m1", resume=True, timeout_s=15.0)
    joined = " ".join(handle.argv)
    assert "CAPT_BRIDGE_NONCE" not in joined
    assert "--nonce" not in joined


def test_ready_socket_survives_deep_workspace_path(tmp_path):
    """Regression: AF_UNIX paths cap at ~104 bytes on macOS.

    A deep workspace path previously raised ``OSError: AF_UNIX path too long``
    from ``_ReadyListener.bind``, which surfaced as a spurious launch failure.
    The listener must relocate to a private 0700 tempdir instead.
    """
    from capt_solo.bridge.runner_process import _ReadyListener

    deep = tmp_path
    for i in range(12):
        deep = deep / f"deeply-nested-directory-segment-{i:02d}"
    deep.mkdir(parents=True)
    assert len(str(deep)) > 100

    listener = _ReadyListener(deep)
    try:
        assert listener.secure()
        assert len(listener.path) <= 104
        assert os.path.exists(listener.path)
    finally:
        listener.close()


def test_launch_never_uses_shell():
    """shell=True is forbidden anywhere in the bridge."""
    src = (REPO / "capt_solo" / "bridge").rglob("*.py")
    for path in src:
        text = path.read_text(encoding="utf-8")
        assert "shell=True" not in text, f"{path} uses shell=True"


# ---------------------------------------------------------------------------
# provider ownership invariant
# ---------------------------------------------------------------------------
def test_exactly_one_provider_owner_initial():
    own = ProviderOwnership()
    assert own.owner == OWNER_HERMES_BEFORE_BRIDGE
    own.assert_single_owner()


def test_transition_to_capt_after_ready():
    own = ProviderOwnership()
    own.transition(OWNER_CAPT_AFTER_READY)
    assert own.owner == OWNER_CAPT_AFTER_READY


def test_no_silent_fallback_to_hermes():
    own = ProviderOwnership()
    own.transition(OWNER_CAPT_AFTER_READY)
    with pytest.raises(ProviderOwnershipViolation):
        own.transition(OWNER_HERMES_BEFORE_BRIDGE)  # unauthorized


def test_authorized_fallback_permitted():
    own = ProviderOwnership()
    own.transition(OWNER_CAPT_AFTER_READY)
    own.transition(OWNER_HERMES_BEFORE_BRIDGE, owner_authorized=True)
    assert own.owner == OWNER_HERMES_BEFORE_BRIDGE


def test_provider_allowed_requires_full_governed_state():
    r = BridgeResult(
        boot_state=BOOT_STATE_FULL, provider_owner=OWNER_CAPT_AFTER_READY,
        memory_use_gate="PASS", execution_mode="GOVERNED",
    )
    assert r.provider_allowed
    for mutation in (
        {"boot_state": BOOT_STATE_PARTIAL},
        {"provider_owner": OWNER_NONE_WHEN_BLOCKED},
        {"memory_use_gate": "BLOCKED"},
        {"execution_mode": "BOOTSTRAP_DEGRADED"},
    ):
        kwargs = {
            "boot_state": BOOT_STATE_FULL,
            "provider_owner": OWNER_CAPT_AFTER_READY,
            "memory_use_gate": "PASS",
            "execution_mode": "GOVERNED",
        }
        kwargs.update(mutation)
        assert not BridgeResult(**kwargs).provider_allowed, mutation


# ---------------------------------------------------------------------------
# Hermes middleware behaviour (the suppression contract)
# ---------------------------------------------------------------------------
def test_provider_blocked_before_ready_does_not_call_next():
    from capt_solo.bridge.hermes_middleware import llm_execution_middleware, reset_session

    session = reset_session()
    session.record_block(blocked("nope", ("RUNNER_DIED",)))
    called = []
    resp = llm_execution_middleware({"messages": []}, lambda req: called.append(req))
    assert called == [], "native provider must NOT be invoked while blocked"
    assert getattr(resp, "bridge_blocked", False) is True
    assert "PROVIDER BLOCKED" in resp.choices[0].message.content


def test_hermes_keeps_ownership_when_bridge_inert():
    from capt_solo.bridge.hermes_middleware import llm_execution_middleware, reset_session

    reset_session()
    sentinel = object()
    resp = llm_execution_middleware({"messages": []}, lambda req: sentinel)
    assert resp is sentinel, "inert bridge must pass through to Hermes"


def test_middleware_never_raises_even_on_internal_error(monkeypatch):
    """Raising is FAIL-OPEN in Hermes; the bridge must return a blocked response."""
    import capt_solo.bridge.hermes_middleware as hm

    session = hm.reset_session()
    session.record_ready(
        BridgeResult(
            boot_state=BOOT_STATE_FULL, provider_owner=OWNER_CAPT_AFTER_READY,
            memory_use_gate="PASS", execution_mode="GOVERNED",
        )
    )

    def explode(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(hm, "_capt_turn", explode)
    called = []
    resp = hm.llm_execution_middleware({"messages": []}, lambda req: called.append(req))
    assert called == [], "internal error must NOT fall through to the native provider"
    assert getattr(resp, "bridge_blocked", False) is True


def test_runner_crash_after_ready_blocks_without_fallback():
    import capt_solo.bridge.hermes_middleware as hm
    from capt_solo.bridge.runner_process import RunnerHandle

    session = hm.reset_session()
    dead = RunnerHandle(argv=(), pid=999_999_999)
    session.record_ready(
        BridgeResult(
            boot_state=BOOT_STATE_FULL, provider_owner=OWNER_CAPT_AFTER_READY,
            memory_use_gate="PASS", execution_mode="GOVERNED", mission_id="m1",
        ),
        handle=dead,
    )
    called = []
    resp = hm.llm_execution_middleware({"messages": []}, lambda req: called.append(req))
    assert called == []
    assert getattr(resp, "bridge_blocked", False) is True
    assert "RUNNER_DIED" in resp.choices[0].message.content


def test_explicit_authorization_allows_hermes_fallback(monkeypatch):
    import capt_solo.bridge.hermes_middleware as hm

    session = hm.reset_session()
    session.record_block(blocked("dead", ("RUNNER_DIED",)))
    monkeypatch.setenv(hm.FALLBACK_AUTH_ENV, "1")
    sentinel = object()
    resp = hm.llm_execution_middleware({"messages": []}, lambda req: sentinel)
    assert resp is sentinel, "explicit owner authorization must permit fallback"


def test_intent_extraction_from_hermes_request():
    from capt_solo.bridge.hermes_middleware import _extract_intent

    assert _extract_intent({"messages": [{"role": "user", "content": "hello"}]}) == "hello"
    assert (
        _extract_intent(
            {"messages": [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]}
        )
        == "hi"
    )


def test_middleware_kind_is_valid_in_hermes():
    from capt_solo.bridge.hermes_plugin import MIDDLEWARE_KIND

    assert MIDDLEWARE_KIND == "llm_execution"


def test_plugin_registers_middleware():
    from capt_solo.bridge.hermes_plugin import register

    registered = []

    class Ctx:
        def register_middleware(self, kind, cb):
            registered.append((kind, cb))

    register(Ctx())
    assert registered and registered[0][0] == "llm_execution"


def test_plugin_degrades_when_host_lacks_middleware():
    from capt_solo.bridge.hermes_plugin import register

    class Ctx:
        pass

    register(Ctx())  # must not raise


# ---------------------------------------------------------------------------
# ownership guard
# ---------------------------------------------------------------------------
def test_external_skill_mutation_denied(tmp_path):
    from capt_solo.bridge.ownership_guard import DENIAL_CODE, RuntimeOwnershipGuard

    guard = RuntimeOwnershipGuard([str(tmp_path)], receipts_dir=tmp_path / "receipts")
    denial = guard.check(str(Path.home() / ".hermes" / "skills" / "evil" / "SKILL.md"))
    assert denial is not None
    assert denial.code == DENIAL_CODE
    assert guard.denials


def test_global_hermes_config_mutation_denied(tmp_path):
    from capt_solo.bridge.ownership_guard import RuntimeOwnershipGuard

    guard = RuntimeOwnershipGuard([str(tmp_path)])
    assert guard.check(str(Path.home() / ".hermes" / "config.yaml")) is not None
    assert guard.check(str(Path.home() / ".hermes" / "auth.json")) is not None


def test_arbitrary_home_write_denied(tmp_path):
    from capt_solo.bridge.ownership_guard import RuntimeOwnershipGuard

    guard = RuntimeOwnershipGuard([str(tmp_path)])
    assert guard.check(str(Path.home() / "random.txt")) is not None


def test_workspace_write_allowed(tmp_path):
    from capt_solo.bridge.ownership_guard import RuntimeOwnershipGuard

    guard = RuntimeOwnershipGuard([str(tmp_path)])
    assert guard.check(str(tmp_path / "src" / "file.py")) is None


def test_explicit_scope_authorization(tmp_path, monkeypatch):
    from capt_solo.bridge.ownership_guard import AUTHORIZATION_ENV, RuntimeOwnershipGuard

    other = tmp_path / "elsewhere"
    other.mkdir()
    guard = RuntimeOwnershipGuard([str(tmp_path / "ws")])
    assert guard.check(str(other / "f.txt")) is not None
    monkeypatch.setenv(AUTHORIZATION_ENV, str(other))
    guard2 = RuntimeOwnershipGuard([str(tmp_path / "ws")])
    assert guard2.check(str(other / "f.txt")) is None


def test_denial_receipt_persisted(tmp_path):
    from capt_solo.bridge.ownership_guard import RuntimeOwnershipGuard

    receipts = tmp_path / "receipts"
    guard = RuntimeOwnershipGuard([str(tmp_path / "ws")], receipts_dir=receipts)
    guard.check(str(Path.home() / ".hermes" / "skills" / "x"))
    files = list(receipts.glob("*.json"))
    assert files, "a denial must leave a receipt"
    body = json.loads(files[0].read_text())
    assert body["code"] == "RUNTIME_OWNERSHIP_DENIAL"
    assert body["receipt_digest"].startswith("sha256:")


def test_guard_enforce_raises(tmp_path):
    from capt_solo.bridge.ownership_guard import OwnershipGuardError, RuntimeOwnershipGuard

    guard = RuntimeOwnershipGuard([str(tmp_path)])
    with pytest.raises(OwnershipGuardError):
        guard.enforce(str(Path.home() / ".hermes" / "skills" / "y"))


def test_unreviewed_historical_mutations_recorded_not_reverted(tmp_path):
    from capt_solo.bridge.ownership_guard import UNREVIEWED_CODE, RuntimeOwnershipGuard

    victim = tmp_path / "owner-file.txt"
    victim.write_text("owner content")
    guard = RuntimeOwnershipGuard([str(tmp_path / "ws")], receipts_dir=tmp_path / "r")
    out = guard.record_unreviewed([str(victim)])
    assert out[0].code == UNREVIEWED_CODE
    assert victim.read_text() == "owner content", "owner files must NEVER be auto-reverted"


# ---------------------------------------------------------------------------
# verification obligations
# ---------------------------------------------------------------------------
def test_unchanged_digest_reuses_prior_evidence(tmp_path):
    from capt_solo.bridge.verification_ledger import ObligationLedger

    src = tmp_path / "s.py"
    src.write_text("x = 1\n")
    tst = tmp_path / "t.py"
    tst.write_text("def test_x(): pass\n")

    ledger = ObligationLedger(tmp_path / "ledger.json")
    ob, must_run = ledger.register(
        "ob1", source_paths=[str(src)], test_paths=[str(tst)], command=["pytest"]
    )
    assert must_run
    ledger.record_result("ob1", passed=True, evidence="1 passed")
    ledger.save()

    # Second identical registration -> NO re-run.
    ledger2 = ObligationLedger(tmp_path / "ledger.json")
    ob2, must_run2 = ledger2.register(
        "ob1", source_paths=[str(src)], test_paths=[str(tst)], command=["pytest"]
    )
    assert not must_run2, "unchanged digest must reuse prior evidence"
    assert ob2.executions == 1
    assert ob2.invalidations == 0


def test_changed_source_invalidates_exactly_once(tmp_path):
    from capt_solo.bridge.verification_ledger import ObligationLedger

    src = tmp_path / "s.py"
    src.write_text("x = 1\n")
    tst = tmp_path / "t.py"
    tst.write_text("def test_x(): pass\n")

    ledger = ObligationLedger(tmp_path / "l.json")
    ledger.register("ob1", source_paths=[str(src)], test_paths=[str(tst)], command=["pytest"])
    ledger.record_result("ob1", passed=True, evidence="1 passed")

    src.write_text("x = 2\n")  # relevant source changed
    ob, must_run = ledger.register(
        "ob1", source_paths=[str(src)], test_paths=[str(tst)], command=["pytest"]
    )
    assert must_run
    assert ob.invalidations == 1
    ledger.record_result("ob1", passed=True, evidence="1 passed again")

    # Re-registering with the same (new) content must NOT invalidate again.
    ob2, must_run2 = ledger.register(
        "ob1", source_paths=[str(src)], test_paths=[str(tst)], command=["pytest"]
    )
    assert not must_run2
    assert ob2.invalidations == 1, "exactly one invalidation per real change"
    assert ob2.executions == 2


def test_untracked_file_presence_does_not_trigger_rerun(tmp_path):
    """An unchanged file remaining untracked is NOT grounds for re-running."""
    from capt_solo.bridge.verification_ledger import ObligationLedger

    src = tmp_path / "s.py"
    src.write_text("x = 1\n")
    tst = tmp_path / "t.py"
    tst.write_text("def test_x(): pass\n")

    ledger = ObligationLedger(tmp_path / "l.json")
    ledger.register("ob1", source_paths=[str(src)], test_paths=[str(tst)], command=["pytest"])
    ledger.record_result("ob1", passed=True, evidence="ok")

    (tmp_path / "stray-untracked.txt").write_text("noise")
    (tmp_path / "evidence.json").write_text("{}")  # lingering evidence JSON

    _, must_run = ledger.register(
        "ob1", source_paths=[str(src)], test_paths=[str(tst)], command=["pytest"]
    )
    assert not must_run


def test_removed_temporary_verifier_does_not_trigger_rerun(tmp_path):
    from capt_solo.bridge.verification_ledger import ObligationLedger

    src = tmp_path / "s.py"
    src.write_text("x = 1\n")
    tst = tmp_path / "t.py"
    tst.write_text("def test_x(): pass\n")
    tmpver = tmp_path / "tmp_verify.py"
    tmpver.write_text("print('probe')\n")

    ledger = ObligationLedger(tmp_path / "l.json")
    ledger.register("ob1", source_paths=[str(src)], test_paths=[str(tst)], command=["pytest"])
    ledger.record_result("ob1", passed=True, evidence="ok")

    tmpver.unlink()  # temporary verifier removed — irrelevant to the obligation
    _, must_run = ledger.register(
        "ob1", source_paths=[str(src)], test_paths=[str(tst)], command=["pytest"]
    )
    assert not must_run


def test_failed_result_keeps_obligation_open(tmp_path):
    from capt_solo.bridge.verification_ledger import ObligationLedger

    src = tmp_path / "s.py"
    src.write_text("x = 1\n")
    ledger = ObligationLedger(tmp_path / "l.json")
    ledger.register("ob1", source_paths=[str(src)], test_paths=[], command=["pytest"])
    ledger.record_result("ob1", passed=False, evidence="1 failed")
    _, must_run = ledger.register("ob1", source_paths=[str(src)], test_paths=[], command=["pytest"])
    assert must_run, "a FAIL must not clear the obligation"


def test_environment_change_invalidates(tmp_path, monkeypatch):
    from capt_solo.bridge import verification_ledger as vl

    src = tmp_path / "s.py"
    src.write_text("x = 1\n")
    ledger = vl.ObligationLedger(tmp_path / "l.json")
    ledger.register("ob1", source_paths=[str(src)], test_paths=[], command=["pytest"])
    ledger.record_result("ob1", passed=True, evidence="ok")

    monkeypatch.setattr(vl, "environment_identity", lambda: "sha256:different-env")
    ob, must_run = ledger.register("ob1", source_paths=[str(src)], test_paths=[], command=["pytest"])
    assert must_run
    assert ob.invalidations == 1


# ---------------------------------------------------------------------------
# CLI surface
# ---------------------------------------------------------------------------
def test_bridge_status_cli():
    out = subprocess.run(
        [sys.executable, "capt_cli.py", "--json", "bridge", "status"],
        capture_output=True, text=True, timeout=60, cwd=str(REPO),
    )
    assert out.returncode == 0, out.stderr
    data = json.loads(out.stdout)
    assert data["boot_states"] == [
        BOOT_STATE_FULL, BOOT_STATE_PARTIAL, BOOT_STATE_SKILL_ONLY, BOOT_STATE_UNAVAILABLE,
    ]
    assert data["provider_owners"] == [
        OWNER_HERMES_BEFORE_BRIDGE, OWNER_CAPT_AFTER_READY, OWNER_NONE_WHEN_BLOCKED,
    ]


def test_bridge_boot_requires_mission_cli():
    out = subprocess.run(
        [sys.executable, "capt_cli.py", "--json", "bridge", "boot", "--workspace", "."],
        capture_output=True, text=True, timeout=120, cwd=str(REPO),
    )
    assert out.returncode == 3
    data = json.loads(out.stdout)
    assert BLOCK_MISSION_REQUIRED in data["block_codes"]
    assert data["provider_allowed"] is False


def test_bridge_boot_unknown_mission_fails_closed():
    out = subprocess.run(
        [
            sys.executable, "capt_cli.py", "--json", "bridge", "boot",
            "--workspace", ".", "--mission", "no-such-mission-xyz", "--timeout", "45",
        ],
        capture_output=True, text=True, timeout=180, cwd=str(REPO),
    )
    assert out.returncode == 3
    data = json.loads(out.stdout)
    assert data["provider_allowed"] is False
    assert data["provider_owner"] == OWNER_NONE_WHEN_BLOCKED
    assert data["boot_state"] != BOOT_STATE_FULL


# ---------------------------------------------------------------------------
# no transcript inheritance
# ---------------------------------------------------------------------------
def test_bridge_carries_no_transcript():
    """The bridge must not pass Hermes conversation history into CAPT."""
    text = (REPO / "capt_solo" / "bridge" / "hermes_middleware.py").read_text()
    assert "_extract_intent" in text
    # Only the latest user Intent crosses the boundary; no history forwarding.
    turn = (REPO / "capt_solo" / "bridge" / "turn.py").read_text()
    assert "messages" not in turn, "turn payload must not forward Hermes messages"
