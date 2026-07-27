"""Phase 3H — Execution boundaries + anti-token-extraction hardening tests."""
from __future__ import annotations

import pytest

from capt_solo.execution.boundaries import (
    BoundaryViolation,
    Capabilities,
    ExecutionBoundary,
)


def test_h_consent_default_deny():
    b = ExecutionBoundary()
    res = b.run(subject="skill-a", scope="skill:run",
                capabilities=Capabilities(), func=lambda: "ok")
    assert res.ok is False
    assert res.violation == BoundaryViolation.CONSENT_DENIED.value


def test_h_consent_grant_allows():
    b = ExecutionBoundary()
    b.grant("skill-a", "skill:run", ["execute"])
    res = b.run(subject="skill-a", scope="skill:run",
                capabilities=Capabilities(), func=lambda: "result")
    assert res.ok is True
    assert res.redacted_output == "result"


def test_h_network_default_deny():
    b = ExecutionBoundary()
    b.grant("skill-a", "skill:run", ["execute"])
    # declares network but not granted network op -> denied
    res = b.run(subject="skill-a", scope="skill:run",
                capabilities=Capabilities(allows_network=True),
                func=lambda: "fetched")
    assert res.ok is False
    assert res.violation == BoundaryViolation.NETWORK_EGRESS.value


def test_h_network_granted_allows():
    b = ExecutionBoundary()
    b.grant("skill-a", "skill:run", ["execute", "network"])
    res = b.run(subject="skill-a", scope="skill:run",
                capabilities=Capabilities(allows_network=True,
                                          allows_external_side_effects=True),
                func=lambda: "fetched")
    assert res.ok is True


def test_h_token_leak_refused():
    b = ExecutionBoundary()
    b.grant("skill-a", "skill:run", ["execute"])
    # output contains a secret -> refused at boundary
    res = b.run(subject="skill-a", scope="skill:run",
                capabilities=Capabilities(),
                func=lambda: "api_key=sk-1234567890abcdefsecret")
    assert res.ok is False
    assert res.violation == BoundaryViolation.TOKEN_LEAK.value
    assert res.redacted_output.startswith("[REDACTED")


def test_h_safe_output_passes():
    b = ExecutionBoundary()
    b.grant("skill-a", "skill:run", ["execute"])
    res = b.run(subject="skill-a", scope="skill:run",
                capabilities=Capabilities(),
                func=lambda: {"summary": "build passed 374 tests"})
    assert res.ok is True


def test_h_execution_error_bounded():
    b = ExecutionBoundary()
    b.grant("skill-a", "skill:run", ["execute"])
    res = b.run(subject="skill-a", scope="skill:run",
                capabilities=Capabilities(),
                func=lambda: 1 / 0)
    assert res.ok is False
    assert res.violation == BoundaryViolation.UNSAFE_OUTPUT.value
    # internal error detail not leaked beyond type name
    assert "ZeroDivisionError" in res.detail


def test_h_capability_from_dict():
    cap = __import__("capt_solo.execution.boundaries", fromlist=["capability_from_dict"]).capability_from_dict
    c = cap({"allows_network": True, "declared_outputs": ["x"]})
    assert c.allows_network is True
    assert c.declared_outputs == ["x"]
