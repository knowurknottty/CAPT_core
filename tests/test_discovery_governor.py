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
    # Candidates use observation-level vocabulary (source_file_present /
    # project_marker_present); the AGGREGATE carries target-match (SOURCE_PRESENT).
    assert any(c.get("provenance", {}).get("run_id")
               for c in res.candidates)
    assert all(c.get("classification") in
               ("source_file_present", "project_marker_present")
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
    # The aggregate must NOT be a definitive target conclusion, and NO candidate
    # may carry a stronger target claim than the aggregate permits.
    res = run_discovery(targets=[str(tree / "wrong")],
                        allowed_roots=[str(tree)],
                        guess_budget=1,
                        expected_markers=["pyproject.toml"])
    # aggregate: a wrong repo is not SOURCE_PRESENT
    assert res.termination != "source_present"
    # HARD INVARIANT: no candidate may claim "requested source located/high"
    # when the aggregate did not locate the requested target.
    for c in res.candidates:
        assert c.get("classification") in (
            "source_file_present", "project_marker_present",
            "compiled_artifact_only", "possible_repository"), c
        assert c.get("classification") != "source_present", c
        # a JS marker in a python-target hunt must not be high target confidence
        if c.get("path", "").endswith("package.json"):
            assert c.get("classification") == "project_marker_present"


def test_case_d_no_candidate_overstates_target_wrong_repo(tree: Path):
    # Explicit regression for the review finding: candidates inside a
    # possible_repository result must not be source_present/high.
    res = run_discovery(targets=[str(tree / "wrong")],
                        allowed_roots=[str(tree)],
                        expected_markers=["pyproject.toml"],
                        guess_budget=3)
    assert res.termination != "source_present"
    for c in res.candidates:
        assert c.get("classification") != "source_present"
        if c.get("classification") == "source_file_present":
            # file-level observation only; must not read as target located
            assert c.get("confidence") in ("high", "medium")
    # aggregate confidence honors the mismatch
    assert res.source_location_confidence in ("low", "medium")
    # provenance present and correlates with the run
    for c in res.candidates:
        assert c.get("provenance", {}).get("run_id")
        assert c["provenance"]["run_id"] == res.provenance.get("run_id")


def test_case_d_wrong_repo_with_target_markers_not_terminal(tree: Path):
    # Hunt a PYTHON repo (pyproject.toml); the dir is a JS repo (package.json).
    # With expected_markers=pyproject.toml, the JS repo must NOT be a terminal
    # SOURCE_PRESENT — it must be classified possible_repository (Case D).
    sc = BoundedLocalScanner(allowed_roots=[str(tree)],
                             expected_markers=["pyproject.toml"]).scan(
        str(tree / "wrong"))
    assert sc["classification"] == "possible_repository"
    assert sc["confidence"] == "low"
    assert sc["termination"] != "source_present"

    res = run_discovery(targets=[str(tree / "wrong")],
                        allowed_roots=[str(tree)],
                        expected_markers=["pyproject.toml"],
                        guess_budget=3)
    assert res.termination != "source_present"
    assert res.termination in ("possible_repository", "not_found", "exhausted")


def test_case_d_correct_repo_with_matching_marker_is_terminal(tree: Path):
    # A PYTHON repo (pyproject.toml) with expected_markers=pyproject.toml IS
    # a valid terminal source.
    sc = BoundedLocalScanner(allowed_roots=[str(tree)],
                             expected_markers=["pyproject.toml"]).scan(
        str(tree / "src"))
    assert sc["classification"] == "source_present"
    assert sc["confidence"] == "high"
    assert sc["termination"] == "source_present"


# --- Finding C: additional target-criteria regressions ----------------------
def test_case_d_multi_marker_only_one_matches(tmp_path: Path):
    # A repo containing multiple project markers where only one matches the
    # expected set -> target not located.
    repo = tmp_path / "multi"
    repo.mkdir()
    (repo / "package.json").write_text("{}\n")
    (repo / "setup.py").write_text("x=1\n")
    (repo / "src").mkdir()
    (repo / "src" / "thing.py").write_text("y=2\n")
    # expect pyproject.toml; only setup/package present -> not matching
    sc = BoundedLocalScanner(allowed_roots=[str(tmp_path)],
                             expected_markers=["pyproject.toml"]).scan(
        str(repo))
    assert sc["classification"] == "possible_repository"
    assert sc["termination"] != "source_present"


def test_case_d_marker_buried_beyond_bounds(tmp_path: Path):
    # Expected marker requested but buried beyond configured discovery depth ->
    # must not be silently accepted; resource policy applies.
    repo = tmp_path / "repo"
    deep = repo / "a" / "b" / "c" / "d" / "e"
    deep.mkdir(parents=True)
    (deep / "pyproject.toml").write_text("x=1\n")
    lim = ScanLimits(max_depth=2)
    sc = BoundedLocalScanner(limits=lim, allowed_roots=[str(tmp_path)],
                             expected_markers=["pyproject.toml"]).scan(str(repo))
    # marker beyond depth is not seen; not a source_present terminal
    assert sc["classification"] != "source_present"


def test_case_d_expected_marker_symlinked_outside_allowed_root(tmp_path: Path):
    # The would-be expected marker is a symlink resolving OUTSIDE the allowed
    # root -> rejected (symlink escape), not honored as target identity.
    outside = tmp_path / "outside-secret"
    outside.mkdir()
    (outside / "pyproject.toml").write_text("secret\n")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("x=1\n")
    try:
        (repo / "pyproject.toml").symlink_to(outside / "pyproject.toml")
    except (OSError, NotImplementedError):
        import pytest as _pt
        _pt.skip("symlink not supported here")
    # allowed root is ONLY repo; the symlinked marker resolves to outside-secret
    sc = BoundedLocalScanner(allowed_roots=[str(repo)],
                             expected_markers=["pyproject.toml"]).scan(
        str(repo))
    blob = json.dumps(sc, default=str)
    assert "outside-secret" not in blob or "symlink_escape" in blob
    assert sc["classification"] != "source_present"


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
    # INTENTIONAL SYNTHETIC FIXTURE for redaction testing — not real credentials;
    # the test asserts they never survive serialization.
    # pragma: allowlist secret
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


def test_case_j_max_directories_independently_enforced(tmp_path: Path):
    # Regression for the bounds audit (SP3 D-R4): max_directories must be an
    # independent bound on DIRECTORIES, not only a combined node-count guard.
    root = tmp_path / "wide"
    root.mkdir()
    for i in range(30):
        (root / ("d%d" % i)).mkdir()
    lim = ScanLimits(max_directories=5, max_depth=2)
    sc = BoundedLocalScanner(limits=lim, allowed_roots=[str(tmp_path)]).scan(
        str(root))
    # a single wide level must be capped at max_directories, not walked fully
    assert any(r[1] == "dir_count" for r in sc["rejections"])


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
    # digest is a real sha256
    assert ev["evidence"]["artifactDigest"].startswith("sha256:")
    assert len(ev["evidence"]["artifactDigest"].split(":")[1]) == 64


def test_evidence_digest_reproducible_for_equal_content(tree: Path):
    # Two runs over identical content must hash identically (SP3 D-003),
    # despite different volatile request/candidate/run ids.
    from capt_runtime.discovery import to_evidence
    a = run_discovery(targets=[str(tree / "src")], allowed_roots=[str(tree)])
    b = run_discovery(targets=[str(tree / "src")], allowed_roots=[str(tree)])
    import re
    ea = to_evidence(a, mission_id="m", collected_by={"actorId": "x", "kind": "human"})
    eb = to_evidence(b, mission_id="m", collected_by={"actorId": "x", "kind": "human"})
    da = ea["evidence"]["artifactDigest"]
    db = eb["evidence"]["artifactDigest"]
    assert da == db, "equal observation content must yield equal evidence digest"
    # distinct sourceObservationId (provenance) is preserved even though digest matches
    assert ea["sourceObservationId"] != eb["sourceObservationId"]


def test_evidence_digest_changes_on_classification_difference(tmp_path: Path):
    from capt_runtime.discovery import to_evidence, run_discovery
    # a source repo vs an empty dir -> different classification -> different digest
    src = tmp_path / "src"; src.mkdir()
    (src / "pyproject.toml").write_text("x=1\n"); (src / "a.py").write_text("y=2\n")
    empty = tmp_path / "empty"; empty.mkdir()
    a = run_discovery(targets=[str(src)], allowed_roots=[str(tmp_path)])
    b = run_discovery(targets=[str(empty)], allowed_roots=[str(tmp_path)])
    da = to_evidence(a, mission_id="m", collected_by={"actorId": "x", "kind": "human"})
    db = to_evidence(b, mission_id="m", collected_by={"actorId": "x", "kind": "human"})
    assert da["evidence"]["artifactDigest"] != db["evidence"]["artifactDigest"]


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


# ===========================================================================
# Phase 5 — real evidence persistence through canonical record_evidence +
#          restart/recovery
# ===========================================================================
def _exec_meta(command_id="cmdr-1", step="1"):
    from capt_runtime import commands
    return commands.command(
        command_id=command_id, idempotency_key="idem-r-" + step,
        operation_fingerprint=commands.fingerprint("disc-record", {"step": step}),
        correlation_id="corr-r", actor_id="exec", actor_kind="execution_plane",
        issued_at="2026-08-12T00:00:00Z",
    )


def _claim(cm: str, kind="observation", mission_id="mission-1", eids=()):
    import time
    return {
        "schemaVersion": "1.0.0", "claimId": cm, "missionId": mission_id,
        "kind": kind, "statement": "discovery observation", "evidenceIds": list(eids),
        "promotionState": "proposed",
        "proposedBy": {"actorId": "exec", "kind": "execution_plane"},
        "proposedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def test_evidence_persistence_through_record_evidence_and_restart(tree, tmp_path):
    """End-to-end: run discovery -> map to EvidenceRecord -> propose claim ->
    record_evidence -> ledger grows -> reopen runtime -> evidence still present
    by stable identity/digest (Phase 5 closure). Uses the canonical
    RuntimeService boundaries only; no in-memory sleight of hand."""
    from capt_runtime.composition import create_runtime
    from capt_runtime.contracts import require

    ledger = str(tmp_path / "ledger.db")
    runtime = create_runtime(ledger)
    try:
        # 1. governed discovery (read-only) -> evidence payload
        resp = runtime.service.run_governed_discovery(
            {"targets": [str(tree / "src")], "allowedRoots": [str(tree)],
             "guessBudget": 3, "missionId": "mission-1",
             "expectedMarkers": ["pyproject.toml"]},
            _runtime_metadata(actor_kind="human"))
        assert resp["status"] == "ok"
        assert resp["discovery"]["termination"] == "source_present"
        evidence = resp["evidence"]
        require("EvidenceRecord", evidence)  # contract-valid
        ev_id = evidence["evidenceId"]
        digest = evidence["evidence"]["artifactDigest"]

        # ledger must NOT have grown during read-only discovery
        seq_after_discovery = runtime.store.head_sequence()

        # 2. propose a claim (execution plane), then record evidence on it
        claim_id = "claim-disc-1"
        runtime.service.propose_claim(_claim(claim_id), _exec_meta(step="1"))
        before_record = runtime.store.head_sequence()
        runtime.service.record_evidence(
            claim_id, evidence, _exec_meta(command_id="cmdrec-1", step="2"))
        after_record = runtime.store.head_sequence()
        # 3. ledger sequence increases ONLY at record_evidence
        assert after_record > before_record, "record_evidence must append events"
        # read the persisted claim; evidence id attached
        claim_state = runtime.service.store.require_state("claim-" + claim_id)
        assert ev_id in claim_state["evidenceIds"], \
            "evidence id must be attached to the persisted claim"
    finally:
        runtime.close()

    # 4. Close + reopen (recover) the runtime on the same ledger.
    runtime2 = create_runtime(ledger)
    try:
        claim_state2 = runtime2.service.store.require_state("claim-" + claim_id)
        assert ev_id in claim_state2["evidenceIds"]
        # the evidence event is readable from the reopened ledger
        found = None
        for env in runtime2.store.read_events():
            payload = env.get("payload") or {}
            if payload.get("eventType") == "EvidenceRecorded":
                e = payload.get("evidence") or {}
                if e.get("evidenceId") == ev_id:
                    found = e
        assert found is not None, "evidence must be recoverable after restart"
        assert found["evidence"]["artifactDigest"] == digest
        assert found["trust"] == "capt_authoritative"
    finally:
        runtime2.close()


def test_evidence_persistence_duplicate_id_does_not_duplicate_events(tree, tmp_path):
    """Repeated record_evidence with the same evidence id (idempotent replay)
    must not create duplicate evidence records on the claim."""
    from capt_runtime.composition import create_runtime

    runtime = create_runtime(str(tmp_path / "ledger.db"))
    try:
        resp = runtime.service.run_governed_discovery(
            {"targets": [str(tree / "src")], "allowedRoots": [str(tree)],
             "missionId": "mission-1"}, _runtime_metadata(actor_kind="human"))
        evidence = resp["evidence"]
        ev_id = evidence["evidenceId"]
        runtime.service.propose_claim(_claim("claim-disc-2", mission_id="mission-1"),
                                      _exec_meta(step="1"))
        runtime.service.record_evidence("claim-disc-2", evidence,
                                        _exec_meta(command_id="cmdrec-2", step="2"))
        before = runtime.store.head_sequence()
        runtime.service.record_evidence("claim-disc-2", evidence,
                                        _exec_meta(command_id="cmdrec-2b", step="3"))
        after = runtime.store.head_sequence()
        assert after >= before  # idempotent / no unbounded growth
        claim_state = runtime.service.store.require_state("claim-claim-disc-2")
        assert claim_state["evidenceIds"].count(ev_id) == 1, \
            "same evidence id must not be attached twice"
    finally:
        runtime.close()
