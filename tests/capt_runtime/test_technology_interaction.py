from __future__ import annotations

from dataclasses import dataclass

import pytest

from capt_runtime import commands
from capt_runtime.errors import AuthorityViolation
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore


@dataclass
class Clock:
    value: float = 100.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def _meta(tag: str, *, actor_kind: str = "human", actor_id: str = "operator-a"):
    return commands.command(
        command_id=f"cmd-{tag}",
        idempotency_key=f"idem-{tag}",
        operation_fingerprint=commands.fingerprint("tia-test", {"tag": tag}),
        correlation_id=f"corr-{tag}",
        actor_id=actor_id,
        actor_kind=actor_kind,
        issued_at="2026-09-10T18:00:00Z",
    )


def _interaction(risk: str = "observe", **patch):
    value = {
        "interactionId": "interaction-1",
        "actionDigest": "sha256:" + "1" * 64,
        "technology": "browser",
        "targetDigest": "sha256:" + "2" * 64,
        "capabilities": ["dom.read", "page.click"],
        "observationScope": {"targetId": "target-1", "frameId": "main"},
        "riskClass": risk,
        "authorizationAttemptId": "attempt-1",
    }
    value.update(patch)
    return value


@pytest.fixture
def runtime(tmp_path):
    store = EventStore(str(tmp_path / "runtime.db"))
    svc = RuntimeService(store)
    yield store, svc
    store.close()


def _authority(runtime, clock: Clock, *, session_id: str = "sess-a"):
    from desktop.technology_interaction import TechnologyInteractionAuthority

    store, svc = runtime
    return TechnologyInteractionAuthority(
        store,
        svc,
        operator_id="operator-a",
        session_id=session_id,
        monotonic=clock,
        permit_ttl_seconds=30.0,
    )


def test_low_risk_interaction_gets_bound_one_use_permit(runtime):
    clock = Clock()
    authority = _authority(runtime, clock)

    result = authority.authorize(_interaction(), _meta("low-authorize"))

    assert result["status"] == "authorized"
    permit = result["permit"]
    assert permit["interactionId"] == "interaction-1"
    assert permit["actionDigest"] == "sha256:" + "1" * 64
    assert permit["targetDigest"] == "sha256:" + "2" * 64
    assert permit["operatorId"] == "operator-a"
    assert permit["sessionId"] == "sess-a"
    assert permit["remainingUses"] == 1


def test_consequential_interaction_requires_exact_human_approval(runtime):
    clock = Clock()
    authority = _authority(runtime, clock)
    action = _interaction("external_write")

    first = authority.authorize(action, _meta("high-attempt-1"))
    assert first["status"] == "approval_required"
    request = runtime[0].require_state("human_approval-" + first["requestId"])
    binding = request["scope"]["technologyInteraction"]
    assert binding["interactionId"] == action["interactionId"]
    assert binding["actionDigest"] == action["actionDigest"]
    assert binding["targetDigest"] == action["targetDigest"]

    decision = {
        "schemaVersion": "1.0.0",
        "requestId": first["requestId"],
        "decision": "approve",
        "operatorId": "operator-a",
        "decidedAt": "2026-09-10T18:00:05Z",
        "note": None,
        "idempotencyKey": "idem-approve-1",
        "correlationId": "corr-approve-1",
        "sessionId": "sess-a",
    }
    runtime[1].submit_human_approval_decision(
        decision, _meta("approve-1", actor_kind="human")
    )

    second = authority.authorize(
        {**action, "authorizationAttemptId": "attempt-2"},
        _meta("high-attempt-2"),
    )
    assert second["status"] == "authorized"
    assert second["permit"]["actionDigest"] == action["actionDigest"]
    assert second["permit"]["approvalRequestId"] == first["requestId"]


def test_changed_action_under_same_interaction_cannot_reuse_approval(runtime):
    clock = Clock()
    authority = _authority(runtime, clock)
    action = _interaction("external_write")
    first = authority.authorize(action, _meta("mismatch-1"))
    decision = {
        "schemaVersion": "1.0.0",
        "requestId": first["requestId"],
        "decision": "approve",
        "operatorId": "operator-a",
        "decidedAt": "2026-09-10T18:00:05Z",
        "note": None,
        "idempotencyKey": "idem-approve-mismatch",
        "correlationId": "corr-approve-mismatch",
        "sessionId": "sess-a",
    }
    runtime[1].submit_human_approval_decision(
        decision, _meta("approve-mismatch", actor_kind="human")
    )

    changed = {
        **action,
        "actionDigest": "sha256:" + "9" * 64,
        "authorizationAttemptId": "attempt-2",
    }
    with pytest.raises(AuthorityViolation, match="TIA_APPROVAL_BINDING_MISMATCH"):
        authority.authorize(changed, _meta("mismatch-2"))


def test_expired_permit_cannot_be_consumed_or_reissued(runtime):
    clock = Clock()
    authority = _authority(runtime, clock)
    action = _interaction()
    permit = authority.authorize(action, _meta("expiry-auth"))["permit"]
    clock.advance(31.0)

    with pytest.raises(AuthorityViolation, match="TIA_PERMIT_EXPIRED"):
        authority.record_outcome(
            {
                "permitId": permit["permitId"],
                "interactionId": action["interactionId"],
                "actionDigest": action["actionDigest"],
                "targetDigest": action["targetDigest"],
                "phase": "attempted",
                "outcomeDigest": "sha256:" + "3" * 64,
            },
            _meta("expiry-attempt"),
        )

    result = authority.authorize(
        {**action, "authorizationAttemptId": "attempt-2"},
        _meta("expiry-reauth"),
    )
    assert result["status"] == "reconciliation_required"


def test_attempt_consumes_permit_once_then_transport_and_observed_progress(runtime):
    clock = Clock()
    authority = _authority(runtime, clock)
    action = _interaction()
    permit = authority.authorize(action, _meta("phases-auth"))["permit"]
    base = {
        "permitId": permit["permitId"],
        "interactionId": action["interactionId"],
        "actionDigest": action["actionDigest"],
        "targetDigest": action["targetDigest"],
    }

    attempted = authority.record_outcome(
        {**base, "phase": "attempted", "outcomeDigest": "sha256:" + "3" * 64},
        _meta("phases-attempted"),
    )
    assert attempted["phase"] == "attempted"
    assert attempted["remainingUses"] == 0

    with pytest.raises(AuthorityViolation, match="TIA_PERMIT_ALREADY_CONSUMED"):
        authority.record_outcome(
            {**base, "phase": "attempted", "outcomeDigest": "sha256:" + "4" * 64},
            _meta("phases-attempted-again"),
        )

    transported = authority.record_outcome(
        {**base, "phase": "transport", "outcomeDigest": "sha256:" + "5" * 64},
        _meta("phases-transport"),
    )
    assert transported["phase"] == "transport"

    observed = authority.record_outcome(
        {**base, "phase": "observed", "outcomeDigest": "sha256:" + "6" * 64},
        _meta("phases-observed"),
    )
    assert observed["phase"] == "observed"
    assert observed["terminal"] is True


def test_permit_rejects_session_target_and_action_mismatch(runtime):
    clock = Clock()
    authority = _authority(runtime, clock)
    action = _interaction()
    permit = authority.authorize(action, _meta("binding-auth"))["permit"]
    payload = {
        "permitId": permit["permitId"],
        "interactionId": action["interactionId"],
        "actionDigest": action["actionDigest"],
        "targetDigest": action["targetDigest"],
        "phase": "attempted",
        "outcomeDigest": "sha256:" + "7" * 64,
    }

    other_session = _authority(runtime, clock, session_id="sess-b")
    with pytest.raises(AuthorityViolation, match="TIA_PERMIT_SESSION_MISMATCH"):
        other_session.record_outcome(payload, _meta("session-mismatch"))

    with pytest.raises(AuthorityViolation, match="TIA_PERMIT_TARGET_MISMATCH"):
        authority.record_outcome(
            {**payload, "targetDigest": "sha256:" + "8" * 64},
            _meta("target-mismatch"),
        )

    with pytest.raises(AuthorityViolation, match="TIA_PERMIT_ACTION_MISMATCH"):
        authority.record_outcome(
            {**payload, "actionDigest": "sha256:" + "9" * 64},
            _meta("action-mismatch"),
        )


def test_restart_never_resurrects_ephemeral_permit(runtime):
    clock = Clock()
    first = _authority(runtime, clock)
    action = _interaction()
    issued = first.authorize(action, _meta("restart-auth"))
    assert issued["status"] == "authorized"

    restarted = _authority(runtime, clock)
    result = restarted.authorize(
        {**action, "authorizationAttemptId": "attempt-2"},
        _meta("restart-reauth"),
    )
    assert result["status"] == "reconciliation_required"
    assert "permit" not in result


def test_consequential_approval_decision_is_bound_to_original_session(runtime):
    clock = Clock()
    authority = _authority(runtime, clock, session_id="sess-a")
    action = _interaction("external_write")
    first = authority.authorize(action, _meta("approval-session-1"))

    decision = {
        "schemaVersion": "1.0.0",
        "requestId": first["requestId"],
        "decision": "approve",
        "operatorId": "operator-a",
        "decidedAt": "2026-09-10T18:00:05Z",
        "note": None,
        "idempotencyKey": "idem-approval-other-session",
        "correlationId": "corr-approval-other-session",
        "sessionId": "sess-b",
    }
    runtime[1].submit_human_approval_decision(
        decision, _meta("approval-other-session", actor_kind="human")
    )

    with pytest.raises(AuthorityViolation, match="TIA_APPROVAL_SESSION_MISMATCH"):
        authority.authorize(
            {**action, "authorizationAttemptId": "attempt-2"},
            _meta("approval-session-2"),
        )


def test_consequential_approval_persists_only_scope_digest(runtime):
    import json

    clock = Clock()
    authority = _authority(runtime, clock)
    action = _interaction(
        "external_write",
        observationScope={"targetId": "target-1", "privateSentinel": "BETA_SENTINEL_SECRET"},
    )

    first = authority.authorize(action, _meta("scope-digest-1"))
    state = runtime[0].require_state("human_approval-" + first["requestId"])
    stored = state["scope"]["technologyInteraction"]

    assert "observationScope" not in stored
    assert stored["observationScopeDigest"].startswith("sha256:")
    assert "BETA_SENTINEL_SECRET" not in json.dumps(state, sort_keys=True)


def test_capabilities_must_be_nonempty_strings(runtime):
    clock = Clock()
    authority = _authority(runtime, clock)

    for capabilities in (["dom.read", ""], ["dom.read", None], ["dom.read", {"bad": True}]):
        with pytest.raises(AuthorityViolation, match="TIA_CAPABILITIES_INVALID"):
            authority.authorize(
                _interaction(capabilities=capabilities),
                _meta("bad-cap-" + str(len(str(capabilities)))),
            )


def test_authorization_attempt_id_is_preserved_in_permit_provenance(runtime):
    clock = Clock()
    authority = _authority(runtime, clock)
    action = _interaction(authorizationAttemptId="attempt-provenance-7")

    result = authority.authorize(action, _meta("attempt-provenance"))

    assert result["permit"]["authorizationAttemptId"] == "attempt-provenance-7"


def test_unsafe_outcome_metadata_fails_before_permit_consumption(runtime):
    clock = Clock()
    authority = _authority(runtime, clock)
    action = _interaction()
    permit = authority.authorize(action, _meta("unsafe-outcome-auth"))["permit"]
    base = {
        "permitId": permit["permitId"],
        "interactionId": action["interactionId"],
        "actionDigest": action["actionDigest"],
        "targetDigest": action["targetDigest"],
        "phase": "attempted",
        "outcomeDigest": "sha256:" + "3" * 64,
    }

    with pytest.raises(AuthorityViolation, match="TIA_TRANSPORT_DIGEST_REQUIRED"):
        authority.record_outcome(
            {**base, "transportDigest": "raw transport body"},
            _meta("unsafe-transport-digest"),
        )
    with pytest.raises(AuthorityViolation, match="TIA_ROUTE_INVALID"):
        authority.record_outcome(
            {**base, "route": "chromium_cdp\nSECRET"},
            _meta("unsafe-route"),
        )

    accepted = authority.record_outcome(
        {
            **base,
            "transportDigest": "sha256:" + "4" * 64,
            "adapterId": "chromium.cdp-v1",
            "route": "chromium_cdp",
        },
        _meta("safe-outcome"),
    )
    assert accepted["remainingUses"] == 0


def test_approval_expiry_compares_instants_not_iso_text(runtime):
    clock = Clock()
    authority = _authority(runtime, clock)
    action = _interaction("external_write")
    first = authority.authorize(action, _meta("timezone-attempt-1"))
    decision = {
        "schemaVersion": "1.0.0",
        "requestId": first["requestId"],
        "decision": "approve",
        "operatorId": "operator-a",
        "decidedAt": "2026-09-10T18:00:05Z",
        "note": None,
        "idempotencyKey": "idem-timezone-approve",
        "correlationId": "corr-timezone-approve",
        "sessionId": "sess-a",
    }
    runtime[1].submit_human_approval_decision(
        decision, _meta("timezone-approve", actor_kind="human")
    )
    second_meta = _meta("timezone-attempt-2")
    second_meta["issuedAt"] = "2026-09-10T19:01:00+01:00"

    second = authority.authorize(
        {**action, "authorizationAttemptId": "attempt-2"}, second_meta
    )

    assert second["status"] == "authorized"
