#!/usr/bin/env python3
"""Install one verified, signed CAPT.app into both canonical launch paths.

The build script signs a complete bundle first. This helper snapshots both
existing bundles, prepares verified copies beside both destinations, and
rolls both paths back if either replacement or native launch fails.
RuntimeService and its ledger are never touched here.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import time
from uuid import uuid4

BUNDLE_ID = "com.inversionlabs.capt"
EXECUTABLE = "CAPTNativeMac"


class PackagingError(RuntimeError):
    pass


def run(args: list[str], timeout: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=True)


def binary_digest(bundle: Path) -> str:
    binary = bundle / "Contents" / "MacOS" / EXECUTABLE
    if not binary.is_file() or binary.is_symlink():
        raise PackagingError("CAPT_EXECUTABLE_MISSING_OR_SYMLINK")
    return hashlib.sha256(binary.read_bytes()).hexdigest()


def source_marker(bundle: Path) -> str:
    with (bundle / "Contents" / "Info.plist").open("rb") as stream:
        info = plistlib.load(stream)
    if info.get("CFBundleIdentifier") != BUNDLE_ID:
        raise PackagingError("CAPT_BUNDLE_IDENTITY_MISMATCH")
    return str(info.get("CAPTSourceCommit", ""))


def verify_signed_bundle(bundle: Path, expected_commit: str, expected_digest: str) -> None:
    if bundle.is_symlink() or not bundle.is_dir():
        raise PackagingError("CAPT_BUNDLE_NOT_DIRECTORY")
    if source_marker(bundle) != expected_commit:
        raise PackagingError("CAPT_SOURCE_COMMIT_MISMATCH")
    if binary_digest(bundle) != expected_digest:
        raise PackagingError("CAPT_BINARY_DIGEST_MISMATCH")
    try:
        run(["/usr/bin/codesign", "--verify", "--strict", str(bundle)])
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PackagingError("CAPT_BUNDLE_SIGNATURE_INVALID") from exc


def exact_running_pids(executable_paths: set[Path]) -> list[int]:
    output = run(["/bin/ps", "-axo", "pid=,command="]).stdout
    paths = {str(path) for path in executable_paths}
    matches: list[int] = []
    for line in output.splitlines():
        candidate = re.match(r"\s*(\d+)\s+(.+)$", line)
        if candidate and candidate.group(2).strip() in paths:
            matches.append(int(candidate.group(1)))
    return matches


def stop_known_apps(targets: tuple[Path, Path]) -> bool:
    binaries = {target / "Contents" / "MacOS" / EXECUTABLE for target in targets}
    pids = exact_running_pids(binaries)
    if not pids:
        return False
    if len(pids) > 2:
        raise PackagingError("CAPT_RUNNING_PROCESS_SET_AMBIGUOUS")
    try:
        run(["/usr/bin/osascript", "-e", f'tell application id "{BUNDLE_ID}" to quit'], timeout=15)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PackagingError("CAPT_GRACEFUL_QUIT_FAILED") from exc
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if not exact_running_pids(binaries):
            return True
        time.sleep(0.25)
    # Do not escalate to SIGKILL or replace an executable still in use.
    raise PackagingError("CAPT_GRACEFUL_QUIT_TIMED_OUT")


def launch_and_verify(installed: Path) -> None:
    try:
        run(["/usr/bin/open", "-n", str(installed)], timeout=20)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PackagingError("CAPT_LAUNCH_FAILED") from exc
    binary = installed / "Contents" / "MacOS" / EXECUTABLE
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        matches = exact_running_pids({binary})
        if len(matches) == 1:
            time.sleep(1)
            if exact_running_pids({binary}) == matches:
                return
        time.sleep(0.25)
    raise PackagingError("CAPT_LAUNCH_VERIFICATION_FAILED")


def install_signed_bundle(
    signed: Path,
    dist: Path,
    installed: Path,
    backup_root: Path,
    expected_commit: str,
    *,
    validate=None,
    stop=None,
    launch=None,
    after_publish=None,
) -> Path:
    """Atomic per-target replacement and all-target rollback.

    Optional callbacks are test seams; the CLI never exposes or substitutes
    them. All temporary paths are created by this installer and are removed
    only if installation/rollback has completed safely.
    """
    if not re.fullmatch(r"[0-9a-f]{40}", expected_commit):
        raise PackagingError("CAPT_COMMIT_ID_INVALID")
    validate = validate or verify_signed_bundle
    stop = stop or stop_known_apps
    launch = launch or launch_and_verify
    targets = (dist, installed)
    if len({str(x.absolute()) for x in (signed, *targets)}) != 3:
        raise PackagingError("CAPT_BUNDLE_PATH_COLLISION")
    digest = binary_digest(signed)
    validate(signed, expected_commit, digest)

    release_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    backups = backup_root / release_id
    backups.mkdir(mode=0o700, parents=True, exist_ok=False)
    os.chmod(backups, 0o700)

    prepared: list[tuple[Path, Path]] = []
    originals: list[tuple[Path, Path | None]] = []
    published: list[Path] = []
    started = False
    try:
        for target, label in ((dist, "dist"), (installed, "installed")):
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_symlink():
                raise PackagingError("CAPT_TARGET_SYMLINK_REFUSED")
            if target.exists():
                if not target.is_dir():
                    raise PackagingError("CAPT_TARGET_NOT_DIRECTORY")
                # Do not delete or modify prior bundles, even on rollback.
                shutil.copytree(target, backups / f"{label}-before.app", symlinks=True)
            staging_dir = target.parent / f".CAPT-stage-{release_id}-{label}"
            if staging_dir.exists():
                raise PackagingError("CAPT_STAGING_COLLISION")
            staging_dir.mkdir(mode=0o700)
            prepared_bundle = staging_dir / "CAPT.app"
            shutil.copytree(signed, prepared_bundle, symlinks=True)
            validate(prepared_bundle, expected_commit, digest)
            prepared.append((target, prepared_bundle))
        was_running = stop(targets)
        for target, prepared_bundle in prepared:
            hold = target.parent / f".CAPT-preinstall-{release_id}"
            if hold.exists():
                raise PackagingError("CAPT_ROLLBACK_HOLD_COLLISION")
            previous = hold if target.exists() else None
            if previous:
                target.rename(previous)
            originals.append((target, previous))
            prepared_bundle.rename(target)
            published.append(target)
            validate(target, expected_commit, digest)
            if after_publish:
                after_publish(target)
        if binary_digest(dist) != binary_digest(installed):
            raise PackagingError("CAPT_CANONICAL_COPY_DRIFT")
        # Always launch only the canonical installed app, never dist/CAPT.app.
        launch(installed)
        started = True
        for _, previous in originals:
            if previous:
                shutil.rmtree(previous)
        return backups
    except Exception:
        for target, previous in reversed(originals):
            if target in published and target.exists():
                shutil.rmtree(target)
            if previous and previous.exists():
                previous.rename(target)
        # Restore the previous UI only if it was running before this release.
        if "was_running" in locals() and was_running and installed.exists():
            try:
                launch(installed)
            except Exception:
                pass  # Preserve original exception; backups remain for recovery.
        raise
    finally:
        for _, candidate in prepared:
            if candidate.parent.name.startswith(".CAPT-stage-") and candidate.parent.exists():
                shutil.rmtree(candidate.parent)
        # A failed release retains backups for independent recovery.
        if not started:
            print("CAPT_RELEASE_ROLLBACK_BACKUPS=" + str(backups), file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signed", type=Path, required=True)
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--installed", type=Path, required=True)
    parser.add_argument("--backup-root", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    saved = install_signed_bundle(
        args.signed, args.dist, args.installed,
        args.backup_root, args.source_commit,
    )
    print("CAPT_APP_PUBLISHED_COMMIT=" + args.source_commit)
    print("CAPT_APP_INSTALLED=" + str(args.installed))
    print("CAPT_APP_BACKUP=" + str(saved))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
