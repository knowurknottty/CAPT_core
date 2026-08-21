from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT = (ROOT / "docs/CURRENT_STATE.md").read_text()
TOPOLOGY = (ROOT / "docs/PR_TOPOLOGY.md").read_text()
README = (ROOT / "README.md").read_text()


def test_current_docs_name_terminal_candidate_and_release_block():
    assert "PR #117" in CURRENT
    assert "33e24146094242d7a88612cea39267ef52a1d2e1" in CURRENT
    assert "IMPLEMENTED_CROSS_SURFACE_VERIFIED_RELEASE_SECURITY_BLOCKED" in CURRENT
    assert "releaseAuthorized=false" in CURRENT


def test_current_docs_separate_main_from_terminal_candidate():
    assert "24cd0a0adea0b54990f94776acd01610590c10c6" in CURRENT
    assert "runtime/product baseline inspected" in CURRENT.lower()
    assert "Resolve the exact current `main` commit from Git" in CURRENT
    assert "PR #122" in CURRENT
    assert "PR #115" in CURRENT
    assert "PR #121" in CURRENT
    assert "not the authority for the newer terminal convergence work" in CURRENT


def test_pr_topology_tracks_current_open_and_superseded_lanes():
    for pr in (111, 116, 117, 119, 122, 89, 91, 93, 95, 97, 104, 108, 109, 110, 112):
        assert f"#{pr}" in TOPOLOGY
    assert "PR #118" in TOPOLOGY and "closed unmerged" in TOPOLOGY
    assert "Inversion Labs edition" in TOPOLOGY


def test_readme_routes_readers_to_current_state_and_pr_topology():
    assert "docs/CURRENT_STATE.md" in README
    assert "docs/PR_TOPOLOGY.md" in README


def test_stale_pr_stack_is_not_described_as_current_authority():
    canonical = "\n".join((CURRENT, TOPOLOGY, README))
    assert "PR #47 is the current" not in canonical
    assert "PR #48 is the current" not in canonical
    assert "PR #49 is the current" not in canonical
