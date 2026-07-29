"""Fail-closed semantic and distribution checks for CAPT Solo releases.

This module is intentionally stdlib-only.  It can run from an installed
artifact while validating a separate source checkout supplied by the caller.
It never mutates the checkout and never performs network I/O.
"""

from __future__ import annotations

import json
import re
import subprocess
import tarfile
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set


MANIFEST_PATH = Path("docs/release/PUBLIC_API_MANIFEST_V0.5.json")
LIVE_STATE_FILES = (
    Path("CURRENT_STATE.md"),
    Path("CHECKPOINT.md"),
    Path("RELEASE_STATE.md"),
)
STALE_STATE_MARKERS = (
    "27ce5fc",
    "integration/full-public-architecture",
    "version `0.4.1`",
    "declared version**: `0.4.1`",
    "M3 Physics engine",
)


@dataclass(frozen=True)
class ReleaseCheck:
    check_id: str
    status: str
    evidence: str


def _check(check_id: str, ok: bool, evidence: str) -> ReleaseCheck:
    return ReleaseCheck(check_id, "pass" if ok else "fail", evidence)


def _read(root: Path, relative: Path) -> str:
    return (root / relative).read_text(encoding="utf-8")


def _match(pattern: str, text: str, source: str) -> str:
    found = re.search(pattern, text, flags=re.MULTILINE)
    if not found:
        raise ValueError(f"could not read version from {source}")
    return found.group(1)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _source_packages(root: Path) -> Set[str]:
    package_root = root / "capt_solo"
    packages = set()
    for init in package_root.rglob("__init__.py"):
        relative = init.parent.relative_to(root)
        if "__pycache__" not in relative.parts:
            packages.add(".".join(relative.parts))
    return packages


def _declared_packages(manifest: dict) -> Set[str]:
    packages = manifest.get("packages", {})
    return {
        package
        for tier in ("stable", "provisional", "experimental")
        for package in packages.get(tier, [])
    }


def _artifact_names(path: Path) -> Set[str]:
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            return set(archive.namelist())
    if path.name.endswith(".tar.gz"):
        with tarfile.open(path, "r:gz") as archive:
            names = set()
            for name in archive.getnames():
                parts = Path(name).parts
                names.add("/".join(parts[1:]) if len(parts) > 1 else name)
            return names
    raise ValueError(f"unsupported distribution artifact: {path}")


def _artifact_packages(names: Iterable[str]) -> Set[str]:
    packages = set()
    for name in names:
        if not name.startswith("capt_solo/") or not name.endswith("/__init__.py"):
            continue
        packages.add(name[: -len("/__init__.py")].replace("/", "."))
    if "capt_solo/__init__.py" in names:
        packages.add("capt_solo")
    return packages


def _validate_artifact(path: Path, expected_packages: Set[str]) -> List[ReleaseCheck]:
    checks: List[ReleaseCheck] = []
    try:
        names = _artifact_names(path)
    except Exception as exc:
        return [_check(
            f"artifact.{path.name}.readable",
            False,
            f"{type(exc).__name__}: {exc}",
        )]

    actual_packages = _artifact_packages(names)
    checks.append(_check(
        f"artifact.{path.name}.packages",
        actual_packages == expected_packages,
        f"expected={sorted(expected_packages)} actual={sorted(actual_packages)}",
    ))
    required = {
        "capt_solo/plugin/plugin.json",
        "capt_cli.py",
    }
    skill_count = sum(
        1
        for name in names
        if name.startswith("capt_solo/skills/") and name.endswith("/SKILL.md")
    )
    checks.append(_check(
        f"artifact.{path.name}.data",
        required.issubset(names) and skill_count == 8,
        f"required_present={required.issubset(names)} skill_count={skill_count}",
    ))
    forbidden = sorted(
        name
        for name in names
        if (
            name.startswith(("tests/", ".capt/", ".capt_state/"))
            or "/.capt/" in name
            or "/.capt_state/" in name
            or name.endswith((".pem", ".key", ".db"))
        )
    )
    checks.append(_check(
        f"artifact.{path.name}.private_files",
        not forbidden,
        f"forbidden={forbidden}",
    ))
    return checks


def validate_release(
    root: Path,
    *,
    dist_dir: Optional[Path] = None,
    final: bool = False,
    candidate_sha: Optional[str] = None,
) -> List[ReleaseCheck]:
    """Return all release checks without mutating *root*."""

    root = root.resolve()
    checks: List[ReleaseCheck] = []

    required_paths = (
        Path("pyproject.toml"),
        Path("capt_solo/__init__.py"),
        Path("capt_solo/plugin/plugin.json"),
        Path("capt_solo/foundry/bubble.py"),
        Path("capt_solo/memory/engine.py"),
        MANIFEST_PATH,
        Path("README.md"),
        Path("CHANGELOG.md"),
        Path("docs/CHANGELOG.md"),
        Path("docs/PUBLIC_ARCHITECTURE.md"),
        Path("docs/PUBLIC_API_STABILITY.md"),
        Path("docs/DATA_MODEL.md"),
        Path("docs/MIGRATIONS.md"),
        Path("docs/tutorials/VERIFY_AI_WORK_IN_FIVE_MINUTES.md"),
    )
    missing = [str(path) for path in required_paths if not (root / path).is_file()]
    checks.append(_check("authority.required_paths", not missing, f"missing={missing}"))
    if missing:
        return checks

    manifest = json.loads(_read(root, MANIFEST_PATH))
    version_sources = {
        "pyproject.toml": _match(
            r'^version\s*=\s*"([^"]+)"',
            _read(root, Path("pyproject.toml")),
            "pyproject.toml",
        ),
        "capt_solo/__init__.py": _match(
            r'^__version__\s*=\s*"([^"]+)"',
            _read(root, Path("capt_solo/__init__.py")),
            "capt_solo/__init__.py",
        ),
        "capt_solo/plugin/plugin.json": json.loads(
            _read(root, Path("capt_solo/plugin/plugin.json"))
        )["version"],
        "capt_solo/foundry/bubble.py": _match(
            r'^CAPT_SOLO_VERSION\s*=\s*"([^"]+)"',
            _read(root, Path("capt_solo/foundry/bubble.py")),
            "capt_solo/foundry/bubble.py",
        ),
        str(MANIFEST_PATH): manifest["version"],
    }
    versions = set(version_sources.values())
    checks.append(_check(
        "version.identity",
        len(versions) == 1 and versions == {"0.5.0"},
        json.dumps(version_sources, sort_keys=True),
    ))

    schema_version = int(_match(
        r"^SCHEMA_VERSION\s*=\s*(\d+)",
        _read(root, Path("capt_solo/memory/engine.py")),
        "capt_solo/memory/engine.py",
    ))
    schema_documents = {
        "doctor.sh": _read(root, Path("doctor.sh")),
        "docs/PUBLIC_API_STABILITY.md": _read(
            root, Path("docs/PUBLIC_API_STABILITY.md")
        ),
        "docs/DATA_MODEL.md": _read(root, Path("docs/DATA_MODEL.md")),
        "docs/MIGRATIONS.md": _read(root, Path("docs/MIGRATIONS.md")),
    }
    stale_schema = [
        name
        for name, text in schema_documents.items()
        if (
            "SCHEMA_VERSION=4" in text
            or "SCHEMA_VERSION = 4" in text
            or "Stable schema v4" in text
            or "| schema v4 |" in text
        )
    ]
    declared_current = all(
        (
            "SCHEMA_VERSION=5" in text
            or "SCHEMA_VERSION = 5" in text
            or "schema v5" in text
        )
        for text in schema_documents.values()
    )
    checks.append(_check(
        "schema.identity",
        schema_version == 5 and not stale_schema and declared_current,
        (
            f"runtime={schema_version} stale_documents={stale_schema} "
            f"all_declare_current={declared_current}"
        ),
    ))

    actual_packages = _source_packages(root)
    declared_packages = _declared_packages(manifest)
    checks.append(_check(
        "public_api.package_inventory",
        actual_packages == declared_packages,
        f"declared={sorted(declared_packages)} source={sorted(actual_packages)}",
    ))

    pyproject = _read(root, Path("pyproject.toml"))
    package_config_ok = (
        '"capt_solo"' in pyproject
        and '"capt_solo.*"' in pyproject
        and 'py-modules = ["capt_cli"]' in pyproject
        and 'capt = "capt_cli:main"' in pyproject
    )
    checks.append(_check(
        "packaging.discovery_contract",
        package_config_ok,
        "recursive capt_solo discovery, capt_cli module, and capt entry point required",
    ))

    live_text = "\n".join(_read(root, path) for path in LIVE_STATE_FILES)
    stale = [marker for marker in STALE_STATE_MARKERS if marker in live_text]
    checks.append(_check(
        "authority.live_state_freshness",
        not stale and "0.5.0" in live_text,
        f"stale_markers={stale} version_0_5_present={'0.5.0' in live_text}",
    ))
    checks.append(_check(
        "authority.release_status",
        "NOT RELEASE READY" in live_text and "NOT PUBLISHED" in live_text,
        "live state must explicitly preserve both release and publication gates",
    ))

    current_docs = "\n".join(
        _read(root, path)
        for path in (
            Path("README.md"),
            Path("docs/API.md"),
            Path("capt_solo/__init__.py"),
        )
    ).lower()
    sole_api = re.findall(r"(?:sole|only)\s+(?:supported\s+)?public\s+api", current_docs)
    checks.append(_check(
        "public_api.no_sole_facade_claim",
        not sole_api,
        f"forbidden_claims={sole_api}",
    ))

    docs_changelog = _read(root, Path("docs/CHANGELOG.md"))
    checks.append(_check(
        "authority.changelog_pointer",
        "../CHANGELOG.md" in docs_changelog
        and "history/CHANGELOG_PRE_V0_5.md" in docs_changelog,
        "docs/CHANGELOG.md must point to current and historical authorities",
    ))

    manifest_sha = manifest.get("candidate_sha")
    checks.append(_check(
        "candidate.manifest_state",
        manifest_sha == "UNFROZEN" if not final else manifest_sha != "UNFROZEN",
        f"candidate_sha={manifest_sha}",
    ))

    if final:
        try:
            head = _git(root, "rev-parse", "HEAD")
            expected_sha = candidate_sha or head
            checks.append(_check(
                "candidate.sha_match",
                manifest_sha == expected_sha,
                f"manifest={manifest_sha} expected={expected_sha} head={head}",
            ))
            status = [
                line
                for line in _git(root, "status", "--short").splitlines()
                if ".capt_state/" not in line
            ]
            checks.append(_check(
                "candidate.clean_tree",
                not status,
                f"non_state_changes={status}",
            ))
        except Exception as exc:
            checks.append(_check(
                "candidate.git_state",
                False,
                f"{type(exc).__name__}: {exc}",
            ))

    if dist_dir is not None:
        dist_dir = dist_dir.resolve()
        artifacts: Sequence[Path] = tuple(sorted(dist_dir.glob("*.whl"))) + tuple(
            sorted(dist_dir.glob("*.tar.gz"))
        )
        checks.append(_check(
            "artifact.presence",
            len(artifacts) == 2,
            f"artifacts={[path.name for path in artifacts]}",
        ))
        for artifact in artifacts:
            checks.extend(_validate_artifact(artifact, declared_packages))

    return checks


def result_document(checks: Sequence[ReleaseCheck]) -> dict:
    failures = [check for check in checks if check.status == "fail"]
    return {
        "ok": not failures,
        "summary": {
            "checks": len(checks),
            "passed": len(checks) - len(failures),
            "failed": len(failures),
        },
        "checks": [asdict(check) for check in checks],
    }
