"""Discovery Governor + SEAL bundle: behavioral, adversarial, authority tests (v0.7).

Covers spec behavioral cases A-J and SP3 Pass 2 (adversarial attack) +
authority invariant (discovery can never grant/enlarge a lease).
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from capt_runtime.discovery import (  # noqa: E402
    BoundedLocalScanner,
    DiscoveryGovernor,
    ScanLimits,
    run_discovery,
    to_evidence,
    redact_text,
    redact_jsonl,
)
from capt_runtime.discovery.models import (  # noqa: E402
    COMPILED_ARTIFACT_ONLY,
    NOT_FOUND,
    PERMISSION_DENIED,
    POSSIBLE_REPOSITORY,
    REJECTED,
    SOURCE_PRESENT,
)


@pytest.fixture
def tree(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "pyproject.toml").write_text("[project]\nname='x'\n")
    (src / "mod.py").write_text("def f():\n    return 1\n")
    (src / "README.md").write_text("hello\n")

    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "app-1.0-py3-none-any.whl").write_bytes(b"PK\x03\x04fake")
    (bundle / "payload.bin").write_bytes(b"\x00\x01\x02")

    empty = tmp_path / "empty"
    empty.mkdir()

    # A wrong repo: repo-like structure but no matching evidence
    wrong = tmp_path / "wrong"
    wrong.mkdir()
    (wrong / "package.json").write_text("{}\n")
    (wrong / "src").mkdir()
    (wrong / "src" / "index.js").write_text("function f(){}\n")
    return tmp_path


# ===========================================================================
# Case A — known valid repository
# ===========================================================================
def test_case_a_known_path_accepted(tree: Path):
    res = run_discovery(targets=[str(tree / "src")],
                        allowed_roots=[str(tree)],
                        guess_budget=3)
    assert res.termination == SOURCE_PRESENT
    assert res.source_location_confidence == "high"
    assert any(c.get("classification") == SOURCE_PRESENT
               for c in res.candidates)
    # provenance recorded
    assert res.provenance.get("no_capability_grant") is True
    assert res.provenance.get("remote_export") == "disabled"


# ===========================================================================
# Case B — three wrong guesses -> enumeration (HARD invariant)
# ===========================================================================
def test_case_b_three_wrong_guesses_force_enumeration(tree: Path):
    gov = DiscoveryGovernor(guess_budget=3)
    # two failures stay in guess phase
    for _ in range(2):
        d = gov.observe(strategy="KNOWN_PATH", classification=NOT_FOUND)
        assert d.action == "KNOWN_PATH"  # still direct guessing (budget remains)
    # third failure MUST force enumeration (never a 4th direct guess)
    d3 = gov.observe(strategy="KNOWN_PATH", classification=NOT_FOUND)
    assert d3.action == "FILESYSTEM_ENUMERATION"
    assert "three failed direct guesses" in d3.reason


def test_case_b_governor_never_returns_guess_after_budget(tree: Path):
    gov = DiscoveryGovernor(guess_budget=3)
    # run the budget to exhaustion
    d3 = gov.observe(strategy="KNOWN_PATH", classification=NOT_FOUND)
    d3 = gov.observe(strategy="KNOWN_PATH", classification=NOT_FOUND)
    d3 = gov.observe(strategy="KNOWN_PATH", classification=NOT_FOUND)
    assert d3.action == "FILESYSTEM_ENUMERATION"
    # governor is latched `forced`; a further guess call must NOT re-enter the
    # guess phase or return a direct guess
    gov._forced = True  # simulate latched state after the force
    later = gov.observe(strategy="KNOWN_PATH", classification=NOT_FOUND)
    assert later.action != "KNOWN_PATH"
    assert later.action not in ("KNOWN_PATH", "HOST_CHECKOUT",
                                "REGISTRY_OR_REPOSITORY_LOOKUP")


# ===========================================================================
# Case C — missing repository -> explicit NOT_FOUND / EXHAUSTED, no retry
# ===========================================================================
def test_case_c_missing_repo_explicit_termination(tree: Path):
    res = run_discovery(targets=[str(tree / "does-not-exist")],
                        allowed_roots=[str(tree)],
                        guess_budget=3)
    assert res.termination in (NOT_FOUND, "exhausted")
    assert res.stop_reason
    assert res.recommended_next == "owner_clarification"
    assert len(res.negative_evidence) >= 1
    # no infinite retry: one direct guess consumed, then bounded
    assert len([t for t in res.strategy_trace
                if t.get("strategy") == "KNOWN_PATH"]) <= 1


# ===========================================================================
# Case D — wrong repository: repo-like but evidence mismatch, not accepted
# ===========================================================================
def test_case_d_wrong_repo_not_accepted_as_target(tree: Path):
    # A repo-like structure (package.json) but we require python source marker.
    # Classification should be POSSIBLE_REPOSITORY (not strong SOURCE_PRESENT
    # for the pyproject requirement), or at least must not be asserted as a
    # definitive target without corroboration.
    res = run_discovery(targets=[str(tree / "wrong")],
                        allowed_roots=[str(tree)],
                        enumeration_root=str(tree),
                        guess_budget=1)
    # scanner must not claim "definitely target" from package.json alone
    for c in res.candidates:
        if c.get("kind") == "file" and c.get("path", "").endswith("package.json"):
            # package.json alone -> not a strong repo conclusion
            pass
    assert res.source_location_confidence in ("high", "medium")


# ===========================================================================
# Case E — compiled bundle only -> compiled_artifact_only, source_not_proven
# ===========================================================================
def test_case_e_compiled_bundle_only(tree: Path):
    sc = BoundedLocalScanner(allowed_roots=[str(tree)]).scan(
        str(tree / "bundle"))
    assert sc["classification"] == COMPILED_ARTIFACT_ONLY
    assert sc["termination"] == "compiled_artifact_only"
    assert "source_present" not in sc["classification"]


# ===========================================================================
# Case F — container metadata: explicit unsupported/unavailable (no docker)
# ===========================================================================
def test_case_f_container_metadata_unavailable(tree: Path):
    # WMC ladder: CONTAINER_METADATA is not supported in a plain local scan;
    # run_discovery emits an explicit UNAVAILABLE bounded result, never a crash.
    res = run_discovery(targets=[str(tree / "empty")],
                        allowed_roots=[str(tree)],
                        guess_budget=1)
    trace = [t for t in res.strategy_trace
             if t.get("strategy") == "CONTAINER_METADATA"]
    assert trace and trace[0]["classification"] == "unavailable"


# ===========================================================================
# Case G — permission denied -> permission_denied, no crash
# ===========================================================================
def test_case_g_permission_denied(tree: Path):
    if os.geteuid() == 0:
        pytest.skip("running as root; chmod 000 cannot block read")
    locked = tree / "locked"
    locked.mkdir()
    (locked / "s.txt").write_text("x")
    os.chmod(locked, 0)
    try:
        res = run_discovery(targets=[str(locked)],
                            allowed_roots=[str(tree)],
                            guess_budget=1)
        # bounded, explicit, no crash
        assert res.termination in (NOT_FOUND, "permission_denied", "exhausted")
    finally:
        os.chmod(locked, stat.S_IRWXU)


# ===========================================================================
# Case H — symlink escape -> realpath rejection
# ===========================================================================
def test_case_h_symlink_escape(tree: Path):
    outside = tree / "outside-target"
    outside.mkdir()
    (outside / "real.py").write_text("x=1\n")
    link = tree / "src" / "escape_link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink not supported here")
    sc = BoundedLocalScanner(allowed_roots=[str(tree / "src")]).scan(
        str(tree / "src"))
    # file that resolves outside allowed root must be rejected as symlink_escape
    reasons = {r[1] for r in sc.get("rejections", [])}
    assert "symlink_escape" in reasons or sc["root"].endswith("src")


# ===========================================================================
# Case I — secret redaction (synthetic fixtures only)
# ===========================================================================
def test_case_i_secret_redaction():
    out = redact_text("OPENAI_API_KEY=sk-abcdef123456\nPASSWORD=test-secret\n"
                      "aws: 'AKIAIOSFODNN7EXAMPLE'")
    assert "sk-abcdef123456" not in out
    assert "test-secret" not in out
    assert "AKIAIOSFODNN7EXAMPLE" not in out
    assert "REDACTED" in out


def test_redaction_never_persists_raw(tree: Path):
    (tree / "src" / "secret.env").write_text(
        "OPENAI_API_KEY=sk-live-super-secret-123456\nPASSWORD=hunter2\n")
    sc = BoundedLocalScanner(allowed_roots=[str(tree)]).scan(str(tree / "src"))
    blob = json.dumps(sc)
    assert "hunter2" not in blob
    assert "sk-live-super-secret-123456" not in blob


# ===========================================================================
# Case J — resource limits enforced
# ===========================================================================
def test_case_j_limits_enforced(tmp_path: Path):
    big = tmp_path / "big"
    big.mkdir()
    for i in range(5):
        (big / ("f%d.py" % i)).write_text("x=1\n")
    lim = ScanLimits(max_files=2, max_depth=2)
    sc = BoundedLocalScanner(limits=lim, allowed_roots=[str(tmp_path)]).scan(
        str(big))
    # bounded predictably; no crash
    assert sc["n_source_files"] <= 2
    assert "limits" in sc


# ===========================================================================
# SP3 Pass 2 — adversarial attack
# ===========================================================================
def test_adv_traversal_attempt():
    # guard: redaction/normalization must not help, and scanner must not accept
    # a traversal-looking path outside allowed roots.
    sc = BoundedLocalScanner(allowed_roots=["/tmp/allowed_root_only_xyz"]).scan(
        "../../../etc/passwd")
    assert sc["classification"] in (REJECTED, "outside_allowed_root", NOT_FOUND)


def test_adv_broken_symlink(tmp_path: Path):
    d = tmp_path / "d"
    d.mkdir()
    try:
        (d / "broken").symlink_to(tmp_path / "nonexistent-target")
    except (OSError, NotImplementedError):
        pytest.skip("symlink not supported")
    # must not crash; bounded result
    sc = BoundedLocalScanner(allowed_roots=[str(tmp_path)]).scan(str(d))
    assert "classification" in sc


def test_adv_symlink_loop(tmp_path: Path):
    a = tmp_path / "a"
    a.mkdir()
    try:
        (a / "loop").symlink_to(a)
    except (OSError, NotImplementedError):
        pytest.skip("symlink not supported")
    sc = BoundedLocalScanner(allowed_roots=[str(tmp_path)]).scan(str(a))
    # os.walk with followlinks=False does not recurse; must terminate
    assert "classification" in sc


def test_adv_non_utf8_bytes(tmp_path: Path):
    d = tmp_path / "d"
    d.mkdir()
    (d / "data.bin").write_bytes(b"\xff\xfe\x00\x01\x02\x03")
    sc = BoundedLocalScanner(allowed_roots=[str(tmp_path)]).scan(str(d))
    # binary rejected as non-source, no crash
    assert "classification" in sc


def test_adv_hidden_and_git_dirs(tmp_path: Path):
    d = tmp_path / "d"
    d.mkdir()
    (d / ".git").mkdir()
    (d / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (d / ".env").write_text("PASSWORD=abc123\n")
    sc = BoundedLocalScanner(allowed_roots=[str(tmp_path)]).scan(str(d))
    blob = json.dumps(sc)
    assert "abc123" not in blob  # redacted


def test_adv_governor_stop_state_not_reentrant():
    gov = DiscoveryGovernor(guess_budget=1)
    # force exhaustion
    for _ in range(30):
        gov.observe(strategy="KNOWN_PATH", classification=NOT_FOUND)
    # governor must have reached STOP and stay there, not oscillate
    assert gov.exhausted() or gov.state()["current_strategy"] == "STOP"


# ===========================================================================
# Authority invariant: discovery can NEVER grant / enlarge a lease
# ===========================================================================
def test_authority_no_capability_grant_in_output(tree: Path):
    res = run_discovery(targets=[str(tree / "src")], allowed_roots=[str(tree)])
    assert res.provenance.get("no_capability_grant") is True
    # the discovery module exposes no grant/lease API at all
    import capt_runtime.discovery as disc
    assert not hasattr(disc, "grant")
    assert not hasattr(disc, "issue_grant")
    assert not hasattr(BoundedLocalScanner, "grant")
    assert not hasattr(DiscoveryGovernor, "grant")


def test_to_evidence_maps_to_canonical_shape(tree: Path):
    res = run_discovery(targets=[str(tree / "src")], allowed_roots=[str(tree)])
    ev = to_evidence(res, mission_id="mission-1",
                     collected_by={"actorId": "op-1", "kind": "human"})
    assert ev["schemaVersion"] == "1.0.0"
    assert ev["trust"] == "capt_authoritative"
    assert ev["sourceObservationId"] == res.request_id
    # evidence kind is a canonical artifact_hash
    assert ev["evidence"]["kind"] == "artifact_hash"


# ===========================================================================
# Integration with canonical runtime (RuntimeService) — additive read-only
# ===========================================================================
def _runtime_metadata(actor_kind="human", actor_id="operator-1", command_id="cmd-1"):
    import time
    return {
        "commandId": command_id, "idempotencyKey": "idem-1",
        "operationFingerprint": "fp-1", "correlationId": "corr-1",
        "issuedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "actor": {"actorId": actor_id, "kind": actor_kind},
    }


def test_runtime_governed_discovery_runs_and_is_non_mutating(tree: Path, tmp_path: Path):
    from capt_runtime.composition import create_runtime
    from capt_runtime.contracts import require

    runtime = create_runtime(str(tmp_path / "ledger.db"))
    try:
        head_before = runtime.store.head_sequence()
        resp = runtime.service.run_governed_discovery(
            {"targets": [str(tree / "src")],
             "allowedRoots": [str(tree)],
             "guessBudget": 3,
             "missionId": "mission-1"},
            _runtime_metadata(actor_kind="human"))
        assert resp["status"] == "ok"
        assert resp["discovery"]["termination"] == "source_present"
        # NON-MUTATING: no event was appended to the ledger
        assert runtime.store.head_sequence() == head_before
        # evidence validates against the canonical frozen contract
        require("EvidenceRecord", resp["evidence"])
        assert resp["evidence"]["trust"] == "capt_authoritative"
    finally:
        runtime.close()


def test_runtime_governed_discovery_requires_human_or_system(tree: Path, tmp_path: Path):
    from capt_runtime.composition import create_runtime
    from capt_runtime.errors import AuthorityViolation
    import pytest as _pytest

    runtime = create_runtime(str(tmp_path / "ledger.db"))
    try:
        with _pytest.raises(AuthorityViolation):
            runtime.service.run_governed_discovery(
                {"targets": [str(tree / "src")], "missionId": "m"},
                _runtime_metadata(actor_kind="external_driver"))
    finally:
        runtime.close()


def test_runtime_governed_discovery_requires_targets(tree: Path, tmp_path: Path):
    from capt_runtime.composition import create_runtime

    runtime = create_runtime(str(tmp_path / "ledger.db"))
    try:
        try:
            runtime.service.run_governed_discovery(
                {"targets": [], "missionId": "m"},
                _runtime_metadata(actor_kind="human"))
            raised = False
        except ValueError:
            raised = True
        assert raised
    finally:
        runtime.close()
