from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT = (ROOT / "docs/CURRENT_STATE.md").read_text()
TOPOLOGY = (ROOT / "docs/PR_TOPOLOGY.md").read_text()
README = (ROOT / "README.md").read_text()
ROADMAP = (ROOT / "docs/ROADMAP.md").read_text()
SECURITY = (ROOT / "docs/SECURITY.md").read_text()


def test_docs_record_pr117_as_merged_not_candidate():
    assert "PR #117 was merged" in CURRENT
    assert "4a654a74083cf341f8557983ce256949198a02e7" in CURRENT
    assert "570babeef113943860c1268722200a48639e406d" in CURRENT
    assert "terminal candidate is **PR #117**" not in CURRENT


def test_merge_does_not_erase_release_security_failure():
    canonical = "\n".join((CURRENT, TOPOLOGY, README, ROADMAP, SECURITY))
    assert "32440329043" in canonical
    assert "Release Security" in canonical
    assert "releaseAuthorized=false" in canonical
    assert "Merged does not mean release-certified" in CURRENT


def test_pr_topology_tracks_independent_open_lanes():
    for pr in (89, 91, 93, 95, 97, 104, 108, 109, 110, 112, 119, 111, 116, 99):
        assert f"#{pr}" in TOPOLOGY
    assert "PR #118" in TOPOLOGY and "closed unmerged" in TOPOLOGY
    assert "#122" in TOPOLOGY and "stale/non-mergeable" in TOPOLOGY


def test_readme_routes_to_current_state_and_pr_topology():
    assert "docs/CURRENT_STATE.md" in README
    assert "docs/PR_TOPOLOGY.md" in README


def test_roadmap_no_longer_waits_to_merge_pr117():
    assert "only then merge PR #117" not in ROADMAP
    assert "PR #117 is merged" in ROADMAP


def test_old_candidate_language_is_not_current_authority():
    canonical = "\n".join((CURRENT, README, ROADMAP))
    assert "main is not the authority for the newer terminal convergence work" not in canonical.lower()
    assert "not yet a release-certified protected-main merge" not in canonical


def test_docs_bind_release_security_to_exact_authorized_baseline():
    canonical = "\n".join((CURRENT, TOPOLOGY, README, SECURITY))
    assert "2199c036aa22af33fb3eb0700f63f820a35aa55a" in canonical
    assert "32617740908" in canonical
    assert "21 PASS / 0 FAIL / 0 NOT_VERIFIED / 26 NOT_APPLICABLE" in canonical
    assert "release-security authorized" in canonical.lower()
    assert "Resolve literal current `main` from Git" in canonical


def test_security_docs_keep_release_security_separate_from_artifact_release():
    canonical = "\n".join((CURRENT, README, SECURITY))
    assert "signed/notarized" in canonical or "signed/notarized/distributed" in canonical
    assert "rebuild" in canonical.lower() and "re-hash" in canonical.lower()
