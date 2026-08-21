"""Pinned external authored-skill packs for governed model context.

Authored skills are prompt/context guidance, not executable Skill Foundry
procedures and not CAPT authority. A pack must match an immutable lock before
its text may be placed in a ContextSlice.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

from .errors import CaptRuntimeError


class AuthoredSkillPackViolation(CaptRuntimeError):
    """The external pack failed immutable provenance or integrity validation."""

    category = "integrity"


class AuthoredSkillRequestViolation(AuthoredSkillPackViolation):
    """An operator requested malformed or unavailable authored skill context."""

    category = "validation"


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), *args],
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise AuthoredSkillPackViolation(f"git inspection failed: {exc}") from exc


def _canonical_repo(value: str) -> str:
    value = value.strip().rstrip("/")
    m = re.match(r"git@github\.com:(.+)$", value, re.I)
    if m:
        value = "https://github.com/" + m.group(1)
    if value.lower().startswith("ssh://git@github.com/"):
        value = "https://github.com/" + value.split("github.com/", 1)[1]
    if value.lower().startswith("http://github.com/"):
        value = "https://github.com/" + value.split("github.com/", 1)[1]
    if value.endswith(".git"):
        value = value[:-4]
    return value.lower()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _frontmatter_scalar(text: str, key: str) -> str:
    if not text.startswith("---\n"):
        raise AuthoredSkillPackViolation("SKILL.md missing YAML frontmatter")
    match = re.search(rf"(?m)^{re.escape(key)}:\s*([^\n]+)\s*$", text)
    if not match:
        raise AuthoredSkillPackViolation(f"SKILL.md missing frontmatter {key}")
    return match.group(1).strip().strip("\"'")


def _safe_skill_path(root: Path, relative: str) -> Path:
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts:
        raise AuthoredSkillPackViolation(f"unsafe skill path: {relative}")
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise AuthoredSkillPackViolation(f"symlinked skill path rejected: {relative}")
    resolved = (root / rel).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise AuthoredSkillPackViolation(f"skill path escapes pack: {relative}") from exc
    return resolved

def verify_skill_pack(
    root: str | Path,
    lock: Mapping[str, Any],
    *,
    require_clean: bool = True,
) -> Dict[str, Any]:
    """Verify an authored skill checkout against an immutable lock."""
    given_root = Path(root).expanduser()
    if given_root.is_symlink():
        raise AuthoredSkillPackViolation("skill pack root may not be a symlink")
    root_path = given_root.resolve()
    if not root_path.is_dir():
        raise AuthoredSkillPackViolation(f"skill pack root not found: {root_path}")

    required = (
        "packName", "packVersion", "repository", "ref", "commit", "tree", "skills"
    )
    missing = [key for key in required if key not in lock]
    if missing:
        raise AuthoredSkillPackViolation(f"lock missing fields: {missing}")

    actual_origin = _git(root_path, "remote", "get-url", "origin")
    if _canonical_repo(actual_origin) != _canonical_repo(str(lock["repository"])):
        raise AuthoredSkillPackViolation(
            f"repository origin mismatch: {actual_origin!r}"
        )
    actual_commit = _git(root_path, "rev-parse", "HEAD")
    if actual_commit != str(lock["commit"]):
        raise AuthoredSkillPackViolation("repository commit mismatch")
    actual_tree = _git(root_path, "rev-parse", "HEAD^{tree}")
    if actual_tree != str(lock["tree"]):
        raise AuthoredSkillPackViolation("repository tree mismatch")
    if require_clean and _git(root_path, "status", "--porcelain", "--untracked-files=all"):
        raise AuthoredSkillPackViolation("dirty skill pack checkout rejected")
    verified_skills: List[Dict[str, Any]] = []
    seen = set()
    for item in lock["skills"]:
        name = str(item.get("name", ""))
        version = str(item.get("version", ""))
        relative = str(item.get("path", ""))
        expected = str(item.get("sha256", ""))
        if not name or name in seen:
            raise AuthoredSkillPackViolation(f"invalid/duplicate skill name: {name!r}")
        seen.add(name)
        path = _safe_skill_path(root_path, relative)
        if not path.is_file():
            raise AuthoredSkillPackViolation(f"skill file missing: {relative}")
        data = path.read_bytes()
        actual = _sha256(data)
        if actual != expected:
            raise AuthoredSkillPackViolation(f"skill digest mismatch/tamper: {name}")
        text = data.decode("utf-8")
        if _frontmatter_scalar(text, "name") != name:
            raise AuthoredSkillPackViolation(f"skill name mismatch: {name}")
        if _frontmatter_scalar(text, "version") != version:
            raise AuthoredSkillPackViolation(f"skill version mismatch: {name}")
        verified_skills.append({
            "name": name,
            "version": version,
            "path": relative,
            "contentDigest": "sha256:" + actual,
            "content": text,
        })

    manifest_basis = {
        "packName": lock["packName"], "packVersion": lock["packVersion"],
        "repository": _canonical_repo(str(lock["repository"])),
        "ref": lock["ref"], "commit": actual_commit, "tree": actual_tree,
        "skills": [{k: s[k] for k in ("name", "version", "path", "contentDigest")}
                   for s in verified_skills],
    }
    manifest_digest = "sha256:" + _sha256(
        json.dumps(manifest_basis, sort_keys=True, separators=(",", ":")).encode()
    )
    return {
        "packName": str(lock["packName"]),
        "packVersion": str(lock["packVersion"]),
        "repository": str(lock["repository"]),
        "ref": str(lock["ref"]),
        "commit": actual_commit,
        "tree": actual_tree,
        "manifestDigest": manifest_digest,
        "skills": verified_skills,
    }


def build_skill_context(
    root: str | Path,
    lock: Mapping[str, Any],
    *,
    selected_names: Sequence[str],
) -> Dict[str, Any]:
    """Build bounded ContextSlice material from explicitly selected pinned skills."""
    verified = verify_skill_pack(root, lock)
    by_name = {item["name"]: item for item in verified["skills"]}
    selected: List[Dict[str, Any]] = []
    for name in selected_names:
        if name not in by_name:
            raise AuthoredSkillRequestViolation(f"unknown skill requested: {name}")
        if name not in [item["name"] for item in selected]:
            item = by_name[name]
            selected.append({
                "name": item["name"], "version": item["version"],
                "contentDigest": item["contentDigest"], "content": item["content"],
            })
    if not selected:
        raise AuthoredSkillRequestViolation("at least one authored skill must be selected")
    return {
        "packName": verified["packName"], "packVersion": verified["packVersion"],
        "sourceRepository": verified["repository"], "sourceRef": verified["ref"],
        "sourceCommit": verified["commit"], "sourceTree": verified["tree"],
        "manifestDigest": verified["manifestDigest"],
        "trust": "pinned_external", "skills": selected,
    }


_DEFAULT_CAPT_SKILLS_LOCK = (
    Path(__file__).resolve().parent / "skill_packs" / "CAPT_Skills.lock.json"
)


def load_capt_skills_lock(path: str | Path | None = None) -> Dict[str, Any]:
    """Load CAPT's packaged immutable CAPT_Skills release lock."""
    lock_path = Path(path).expanduser() if path is not None else _DEFAULT_CAPT_SKILLS_LOCK
    try:
        value = json.loads(lock_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise AuthoredSkillPackViolation(f"cannot load CAPT_Skills lock: {exc}") from exc
    if value.get("schemaVersion") != "1.0.0":
        raise AuthoredSkillPackViolation("unsupported CAPT_Skills lock schema")
    return value


def parse_authored_skill_request(payload: Mapping[str, Any]) -> tuple[str | None, List[str]]:
    """Validate explicit operator selection of a local pinned authored-skill pack."""
    root = payload.get("skillPackRoot")
    names = payload.get("skillNames")
    if root is None and names is None:
        return None, []
    if not isinstance(root, str) or not root.strip():
        raise AuthoredSkillRequestViolation("skillPackRoot is required when skillNames are selected")
    if not isinstance(names, list) or not names or len(names) > 16:
        raise AuthoredSkillRequestViolation("skillNames must be a non-empty list of at most 16 names")
    normalized: List[str] = []
    for name in names:
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,127}", name):
            raise AuthoredSkillRequestViolation(f"invalid authored skill name: {name!r}")
        if name in normalized:
            raise AuthoredSkillRequestViolation(f"duplicate authored skill name: {name}")
        normalized.append(name)
    return root, normalized


def prepare_authored_skill_context(
    payload: Mapping[str, Any],
    *,
    lock: Mapping[str, Any] | None = None,
) -> tuple[Dict[str, Any] | None, List[str]]:
    """Verify an explicit skill selection and return the exact frozen input basis."""
    root, names = parse_authored_skill_request(payload)
    if not names:
        return None, []
    context = build_skill_context(
        str(root), lock or load_capt_skills_lock(), selected_names=names
    )
    return context, names


def summarize_skill_context(context: Mapping[str, Any] | None) -> Dict[str, Any] | None:
    """Return provenance-only skill evidence; never echo instruction bodies."""
    if not context:
        return None
    return {
        "packName": context.get("packName"),
        "packVersion": context.get("packVersion"),
        "sourceRepository": context.get("sourceRepository"),
        "sourceRef": context.get("sourceRef"),
        "sourceCommit": context.get("sourceCommit"),
        "sourceTree": context.get("sourceTree"),
        "manifestDigest": context.get("manifestDigest"),
        "trust": context.get("trust"),
        "skills": [
            {"name": item.get("name"), "version": item.get("version"),
             "contentDigest": item.get("contentDigest")}
            for item in context.get("skills", [])
        ],
    }
