"""Transactional CAPT native-app packaging regression tests (no macOS side effects)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import plistlib

import pytest

MODULE = (
    Path(__file__).resolve().parents[2]
    / "capt_ui/surfaces/desktop_swift/script/install_signed_bundle.py"
)
spec = importlib.util.spec_from_file_location("capt_install_signed_bundle_test", MODULE)
assert spec and spec.loader
pkg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pkg)

COMMIT = "a" * 40


def bundle(path: Path, content: bytes, commit: str = COMMIT) -> Path:
    path.mkdir(parents=True)
    output = path / "Contents/MacOS/CAPTNativeMac"
    output.parent.mkdir(parents=True)
    output.write_bytes(content)
    info = path / "Contents/Info.plist"
    with info.open("wb") as f:
        plistlib.dump(
            {"CFBundleIdentifier": "com.inversionlabs.capt", "CAPTSourceCommit": commit},
            f,
        )
    return path


def mock_validate(path: Path, expected_commit: str, digest: str) -> None:
    assert pkg.source_marker(path) == expected_commit
    assert pkg.binary_digest(path) == digest


def paths(tmp_path):
    signed = bundle(tmp_path / "signed/CAPT.app", b"fresh signed app")
    dist = bundle(tmp_path / "source/dist/CAPT.app", b"stale dist app")
    installed = bundle(tmp_path / "Applications/CAPT.app", b"stale installed app")
    return signed, dist, installed, tmp_path / "backups"


def test_publishes_identical_bundles_and_keeps_both_rollback_copies(tmp_path):
    signed, dist, installed, root = paths(tmp_path)
    stopped = []
    launched = []
    backup = pkg.install_signed_bundle(
        signed, dist, installed, root, COMMIT,
        validate=mock_validate,
        stop=lambda targets: stopped.append(targets) or True,
        launch=lambda path: launched.append(path),
    )
    expected = pkg.binary_digest(signed)
    assert pkg.binary_digest(dist) == expected
    assert pkg.binary_digest(installed) == expected
    assert pkg.source_marker(installed) == COMMIT
    assert pkg.binary_digest(backup / "dist-before.app") != expected
    assert pkg.binary_digest(backup / "installed-before.app") != expected
    assert launched == [installed]
    assert stopped == [(dist, installed)]


def test_both_bundles_restore_if_second_swap_fails(tmp_path):
    signed, dist, installed, root = paths(tmp_path)
    old_dist = pkg.binary_digest(dist)
    old_installed = pkg.binary_digest(installed)
    launched = []

    def fail_after_first(target):
        if target == dist:
            raise RuntimeError("INJECTED_PUBLISH_FAILURE")

    with pytest.raises(RuntimeError, match="INJECTED_PUBLISH_FAILURE"):
        pkg.install_signed_bundle(
            signed, dist, installed, root, COMMIT,
            validate=mock_validate,
            stop=lambda targets: True,
            launch=lambda path: launched.append(path),
            after_publish=fail_after_first,
        )
    assert pkg.binary_digest(dist) == old_dist
    assert pkg.binary_digest(installed) == old_installed
    assert launched == [installed]  # Only the restored original is launched.


def test_launch_failure_rolls_back_both_signed_app_locations(tmp_path):
    signed, dist, installed, root = paths(tmp_path)
    old_dist = pkg.binary_digest(dist)
    old_installed = pkg.binary_digest(installed)
    calls = []

    def fail_first_launch(path):
        calls.append(path)
        if len(calls) == 1:
            raise RuntimeError("INJECTED_LAUNCH_FAILURE")

    with pytest.raises(RuntimeError, match="INJECTED_LAUNCH_FAILURE"):
        pkg.install_signed_bundle(
            signed, dist, installed, root, COMMIT,
            validate=mock_validate,
            stop=lambda targets: True,
            launch=fail_first_launch,
        )
    assert pkg.binary_digest(dist) == old_dist
    assert pkg.binary_digest(installed) == old_installed
    assert calls == [installed, installed]


def test_invalid_source_commit_stops_before_any_copy(tmp_path):
    signed, dist, installed, root = paths(tmp_path)
    before = pkg.binary_digest(installed)
    with pytest.raises(pkg.PackagingError, match="COMMIT_ID_INVALID"):
        pkg.install_signed_bundle(
            signed, dist, installed, root, "not-a-commit",
            validate=mock_validate,
        )
    assert not root.exists()
    assert pkg.binary_digest(installed) == before


def test_identity_mismatch_stops_before_replacing_anything(tmp_path):
    signed, dist, installed, root = paths(tmp_path)
    info = signed / "Contents/Info.plist"
    with info.open("wb") as out:
        plistlib.dump({"CFBundleIdentifier": "other.app", "CAPTSourceCommit": COMMIT}, out)
    before = pkg.binary_digest(installed)
    with pytest.raises(pkg.PackagingError, match="BUNDLE_IDENTITY_MISMATCH"):
        pkg.install_signed_bundle(signed, dist, installed, root, COMMIT, validate=mock_validate)
    assert pkg.binary_digest(installed) == before


def test_refuses_symlinked_installed_path(tmp_path):
    signed, dist, installed, root = paths(tmp_path)
    actual = installed.rename(tmp_path / "original-app")
    installed.symlink_to(actual, target_is_directory=True)
    with pytest.raises(pkg.PackagingError, match="TARGET_SYMLINK_REFUSED"):
        pkg.install_signed_bundle(
            signed, dist, installed, root, COMMIT,
            validate=mock_validate,
            stop=lambda _: False,
            launch=lambda _: None,
        )
    assert installed.is_symlink()
    assert pkg.binary_digest(dist) != pkg.binary_digest(signed)


def test_native_release_script_publishes_only_canonical_signed_bundle():
    """Guard against duplicated shell fragments and launching dist/CAPT.app."""
    script = (
        Path(__file__).resolve().parents[2]
        / "capt_ui/surfaces/desktop_swift/script/build_and_run.sh"
    ).read_text()
    assert script.count("swift build --product") == 1
    assert script.count("script/install_signed_bundle.py") == 1
    assert script.count('CAPT_PACKAGE_VERSION="$(') == 1
    assert script.count('INSTALLED_HEAD=""') == 1
    assert '<key>CAPTSourceCommit</key>' in script
    assert '--installed "$INSTALLED_BUNDLE"' in script
    assert '--dist "$DIST_BUNDLE"' in script
    assert '--source-commit "$SOURCE_HEAD"' in script
    assert '/usr/bin/open -n "$BUNDLE"' not in script
    assert 'rm -rf "$BUNDLE"' not in script
    assert "kill \"$pid\"" not in script
