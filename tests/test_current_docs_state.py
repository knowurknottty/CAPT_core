from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT = (ROOT / "docs/CURRENT_STATE.md").read_text()
TOPOLOGY = (ROOT / "docs/PR_TOPOLOGY.md").read_text()
README = (ROOT / "README.md").read_text()
ROADMAP = (ROOT / "docs/ROADMAP.md").read_text()
SECURITY = (ROOT / "docs/SECURITY.md").read_text()
CAPABILITY = (ROOT / "docs/CAPABILITY_MATRIX.md").read_text()
AUTHORED = (ROOT / "docs/AUTHORED_SKILLS.md").read_text()


def test_docs_record_current_merged_milestones():
    canonical = "\n".join((CURRENT, TOPOLOGY, README, ROADMAP, CAPABILITY))
    for pr in (117, 126, 128, 129):
        assert f"#{pr}" in canonical
    assert "3aee7370bac880aed99ce3c9ecfaa6d9ff48101e" in CURRENT


def test_historical_release_failure_is_not_erased():
    canonical = "\n".join((CURRENT, TOPOLOGY, README, ROADMAP, SECURITY))
    assert "32440329043" in canonical
    assert "570babeef113943860c1268722200a48639e406d" in canonical
    assert "Release Security" in canonical


def test_docs_bind_known_authorized_baseline_to_exact_sha():
    canonical = "\n".join((CURRENT, TOPOLOGY, README, SECURITY))
    assert "2199c036aa22af33fb3eb0700f63f820a35aa55a" in canonical
    assert "32617740908" in canonical
    assert "21 PASS / 0 FAIL / 0 NOT_VERIFIED / 26 NOT_APPLICABLE" in canonical
    assert "exact" in canonical.lower() and "sha" in canonical.lower()


def test_toolbroker_receipt_is_not_relabelled_as_squash_merge_sha():
    canonical = "\n".join((CURRENT, TOPOLOGY, README, SECURITY))
    assert "b21ed6e7ff3996d48c756e342b278b69af0d666f" in canonical
    assert "bcfdff9d43b35b5b192cc998b68ce16cc73b9985" in canonical
    assert "different" in canonical.lower() and "sha" in canonical.lower()


def test_open_core_lane_is_upg_020_through_024():
    for pr in (89, 91, 93, 95, 97):
        assert f"#{pr}" in TOPOLOGY
    assert "current open Core PR lane" in TOPOLOGY
    assert "not an open Core-main lane" in TOPOLOGY


def test_public_release_design_is_present_but_not_implemented_by_merge():
    canonical = "\n".join((CURRENT, README, ROADMAP, CAPABILITY))
    assert "PR #128" in canonical
    assert "Secure Intake" in canonical
    assert "implementation not claimed" in canonical.lower() or "not thereby implemented" in canonical.lower()


def test_managed_authored_skills_are_documented_as_non_authoritative():
    canonical = "\n".join((README, AUTHORED, CAPABILITY))
    assert "managed_local" in canonical
    assert "pinned_external" in canonical
    assert "capt skills import" in canonical
    assert "capt skills verify" in canonical
    assert "32,768" in canonical
    assert "cannot grant" in canonical.lower()


def test_toolbroker_is_documented_as_governed_not_parallel_authority():
    canonical = "\n".join((CURRENT, README, CAPABILITY))
    assert "ToolBroker" in canonical
    assert "local" in canonical and "ssh" in canonical and "docker" in canonical
    assert "RuntimeService" in canonical and "EventStore" in canonical


def test_current_main_m0a_observation_is_not_hidden():
    canonical = "\n".join((CURRENT, TOPOLOGY, README, ROADMAP, SECURITY))
    assert "32958741310" in canonical
    assert "Python 3.10" in canonical
    assert "Docker" in canonical
    assert "timed out" in canonical.lower() or "timeout" in canonical.lower()


def test_readme_routes_to_current_docs():
    for path in (
        "docs/CURRENT_STATE.md",
        "docs/PR_TOPOLOGY.md",
        "docs/AUTHORED_SKILLS.md",
        "docs/CAPABILITY_MATRIX.md",
        "docs/FUNCTIONALITY_MATRIX.md",
        "docs/SECURITY.md",
        "docs/RELEASE_EVIDENCE.md",
    ):
        assert path in README


def test_security_docs_keep_release_security_separate_from_artifact_release():
    canonical = "\n".join((CURRENT, README, SECURITY))
    assert "signed/notarized" in canonical or "signed/notarized/distributed" in canonical
    assert "rebuild" in canonical.lower() and "hash" in canonical.lower()
