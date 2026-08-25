"""Managed local Agent Skills packs for governed CAPT authored context.

The managed pack is an installed, digest-bound snapshot under a CAPT state root.
It is not authority: selected text remains context-only guidance and is frozen
before prompt approval exactly like CAPT's pinned external authored skills.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from .errors import CaptRuntimeError

_SCHEMA_VERSION = "1.0.0"
_INLINE_CONTENT_LIMIT = 32768
_SKILL_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,127}$")
_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
    "into", "is", "it", "of", "on", "or", "that", "the", "this", "to", "use",
    "user", "when", "with", "work", "working", "wants", "want", "should", "can",
    "do", "does", "make", "making", "task", "tasks", "skill", "skills",
}


class ManagedSkillPackViolation(CaptRuntimeError):
    """A managed local skill pack failed import, integrity, or selection checks."""

    category = "integrity"


@dataclass(frozen=True)
class _Candidate:
    name: str
    description: str
    version: str
    text: str
    skill_dir: Path | None
    flat_file: Path | None
    source_origin: str
    source_kind: str
    triggers: tuple[str, ...]

    @property
    def content_digest(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _clean_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _frontmatter(text: str) -> Dict[str, Any]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end < 0:
        return {}
    lines = text[4:end].splitlines()
    out: Dict[str, Any] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not match:
            i += 1
            continue
        key, raw = match.group(1), match.group(2).strip()
        if raw in {">", ">-", "|", "|-"}:
            i += 1
            parts: List[str] = []
            while i < len(lines) and (not lines[i] or lines[i][0].isspace()):
                if lines[i].strip():
                    parts.append(lines[i].strip())
                i += 1
            out[key] = " ".join(parts) if raw.startswith(">") else "\n".join(parts)
            continue
        if not raw and key in {"triggers"}:
            i += 1
            values: List[str] = []
            while i < len(lines) and (not lines[i] or lines[i][0].isspace()):
                item = re.match(r"^\s*-\s*(.+?)\s*$", lines[i])
                if item:
                    values.append(_clean_scalar(item.group(1)))
                i += 1
            out[key] = values
            continue
        if raw:
            out[key] = _clean_scalar(raw)
        i += 1
    if "version" not in out:
        nested = re.search(r"(?m)^\s{2,}version:\s*([^\n]+)$", text[4:end])
        if nested:
            out["version"] = _clean_scalar(nested.group(1))
    return out


def _candidate_from_text(
    text: str, *, skill_dir: Path | None, flat_file: Path | None,
    source_origin: str, source_kind: str,
) -> _Candidate | None:
    meta = _frontmatter(text)
    name = str(meta.get("name", "")).strip().lower()
    description = str(meta.get("description", "")).strip()
    if not name or not description:
        return None
    if not _SKILL_NAME.fullmatch(name):
        raise ManagedSkillPackViolation(f"invalid skill name: {name!r}")
    raw_triggers = meta.get("triggers", [])
    triggers: List[str] = []
    if isinstance(raw_triggers, list):
        triggers.extend(str(x).strip() for x in raw_triggers if str(x).strip())
    singular = meta.get("trigger")
    if isinstance(singular, str) and singular.strip():
        triggers.append(singular.strip())
    return _Candidate(
        name=name,
        description=description,
        version=str(meta.get("version") or "0.0.0").strip(),
        text=text,
        skill_dir=skill_dir,
        flat_file=flat_file,
        source_origin=source_origin,
        source_kind=source_kind,
        triggers=tuple(triggers),
    )


def _safe_archive_member(name: str) -> bool:
    path = Path(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts


def _extract_skill_bundle(bundle: Path, root: Path) -> Path:
    target = root / (bundle.stem + "-bundle")
    target.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(bundle) as archive:
            for info in archive.infolist():
                if not _safe_archive_member(info.filename):
                    raise ManagedSkillPackViolation(f"unsafe archive path: {info.filename}")
                mode = (info.external_attr >> 16) & 0o170000
                if mode == stat.S_IFLNK:
                    raise ManagedSkillPackViolation(f"symlinked archive member rejected: {info.filename}")
            archive.extractall(target)
    except zipfile.BadZipFile as exc:
        raise ManagedSkillPackViolation(f"invalid .skill archive: {bundle}") from exc
    return target


def _discover_in_tree(root: Path, *, source_kind: str, origin_prefix: str) -> List[_Candidate]:
    candidates: List[_Candidate] = []
    skill_files = sorted(root.rglob("SKILL.md"))
    seen_files = set(skill_files)
    for path in skill_files:
        if path.is_symlink():
            raise ManagedSkillPackViolation(f"symlinked skill file rejected: {path}")
        candidate = _candidate_from_text(
            path.read_text(encoding="utf-8", errors="strict"),
            skill_dir=path.parent,
            flat_file=None,
            source_origin=f"{origin_prefix}:{path.relative_to(root)}",
            source_kind=source_kind,
        )
        if candidate:
            candidates.append(candidate)
    for path in sorted(root.rglob("*.md")):
        if path in seen_files or path.is_symlink():
            continue
        candidate = _candidate_from_text(
            path.read_text(encoding="utf-8", errors="strict"),
            skill_dir=None,
            flat_file=path,
            source_origin=f"{origin_prefix}:{path.relative_to(root)}",
            source_kind="flat",
        )
        if candidate:
            candidates.append(candidate)
    return candidates


def _discover_candidates(source: Path, temp_root: Path) -> List[_Candidate]:
    if source.is_symlink() or not source.is_dir():
        raise ManagedSkillPackViolation(f"skill import source must be a real directory: {source}")
    candidates = _discover_in_tree(source, source_kind="directory", origin_prefix=str(source))
    for bundle in sorted(source.rglob("*.skill")):
        if bundle.is_symlink():
            raise ManagedSkillPackViolation(f"symlinked .skill bundle rejected: {bundle}")
        extracted = _extract_skill_bundle(bundle, temp_root)
        candidates.extend(_discover_in_tree(
            extracted, source_kind="bundle", origin_prefix=str(bundle)
        ))
    return candidates


def _canonicalize_candidates(candidates: Sequence[_Candidate]) -> List[tuple[_Candidate, List[str]]]:
    grouped: Dict[str, List[_Candidate]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.name, []).append(candidate)
    canonical: List[tuple[_Candidate, List[str]]] = []
    for name in sorted(grouped):
        items = grouped[name]
        by_digest: Dict[str, List[_Candidate]] = {}
        for item in items:
            by_digest.setdefault(item.content_digest, []).append(item)
        if len(by_digest) == 1:
            pool = items
        else:
            bundles = [item for item in items if item.source_kind == "bundle"]
            if len({item.content_digest for item in bundles}) == 1 and bundles:
                pool = bundles
            else:
                raise ManagedSkillPackViolation(f"conflicting duplicate skill: {name}")
        preferred = max(pool, key=_candidate_richness)
        canonical.append((preferred, sorted({item.source_origin for item in items})))
    return canonical


def _candidate_richness(candidate: _Candidate) -> tuple[int, int, int]:
    if candidate.skill_dir is None:
        return (0, len(candidate.text), 1 if candidate.source_kind == "bundle" else 0)
    count = 0
    size = 0
    for path in candidate.skill_dir.rglob("*"):
        if path.is_file() and not path.is_symlink():
            count += 1
            size += path.stat().st_size
    return (count, size, 1 if candidate.source_kind == "bundle" else 0)


def _copy_skill(candidate: _Candidate, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    if candidate.flat_file is not None:
        (destination / "SKILL.md").write_text(candidate.text, encoding="utf-8")
        return
    assert candidate.skill_dir is not None
    root = candidate.skill_dir
    nested_skill_dirs = {
        p.parent.resolve() for p in root.rglob("SKILL.md") if p.parent.resolve() != root.resolve()
    }
    for current, dirs, files in os.walk(root):
        current_path = Path(current)
        if current_path.is_symlink():
            raise ManagedSkillPackViolation(f"symlinked skill directory rejected: {current_path}")
        dirs[:] = [d for d in dirs if (current_path / d).resolve() not in nested_skill_dirs]
        rel_dir = current_path.relative_to(root)
        out_dir = destination / rel_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        for filename in files:
            src = current_path / filename
            if src.is_symlink():
                raise ManagedSkillPackViolation(f"symlinked skill content rejected: {src}")
            if src.suffix == ".skill":
                continue
            shutil.copy2(src, out_dir / filename)
    (destination / "SKILL.md").write_text(candidate.text, encoding="utf-8")


def _tree_digest(root: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if path.is_symlink():
            raise ManagedSkillPackViolation(f"symlinked installed skill content rejected: {path}")
        rel = path.relative_to(root).as_posix().encode("utf-8")
        data = path.read_bytes()
        h.update(len(rel).to_bytes(4, "big")); h.update(rel)
        h.update(bytes.fromhex(_sha256(data)))
    return h.hexdigest()


def _manifest_digest(manifest: Mapping[str, Any]) -> str:
    data = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + _sha256(data)


def import_managed_skill_pack(
    source: str | Path, destination: str | Path, *, pack_name: str = "ultimate"
) -> Dict[str, Any]:
    """Import heterogeneous Agent Skills into one atomic managed CAPT pack."""
    source_path = Path(source).expanduser().resolve()
    destination_path = Path(destination).expanduser()
    if not _SKILL_NAME.fullmatch(pack_name):
        raise ManagedSkillPackViolation(f"invalid pack name: {pack_name!r}")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="capt-skill-import-", dir=destination_path.parent))
    build_root = scratch / "pack"; build_root.mkdir()
    try:
        candidates = _discover_candidates(source_path, scratch / "bundles")
        canonical = _canonicalize_candidates(candidates)
        manifest_skills: List[Dict[str, Any]] = []
        for candidate, origins in canonical:
            skill_root = build_root / "skills" / candidate.name
            _copy_skill(candidate, skill_root)
            skill_path = skill_root / "SKILL.md"
            content = skill_path.read_text(encoding="utf-8")
            encoded = content.encode("utf-8")
            manifest_skills.append({
                "name": candidate.name,
                "description": candidate.description,
                "version": candidate.version,
                "path": f"skills/{candidate.name}/SKILL.md",
                "contentDigest": "sha256:" + _sha256(encoded),
                "treeDigest": "sha256:" + _tree_digest(skill_root),
                "contentBytes": len(encoded),
                "inlineable": len(content) <= _INLINE_CONTENT_LIMIT,
                "triggers": list(candidate.triggers),
                "sourceOrigins": origins,
            })
        manifest = {
            "schemaVersion": _SCHEMA_VERSION,
            "packName": pack_name,
            "packVersion": "managed-1",
            "sourceRoots": [str(source_path)],
            "skills": manifest_skills,
        }
        (build_root / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        backup = destination_path.with_name(destination_path.name + ".previous")
        if backup.exists():
            shutil.rmtree(backup)
        if destination_path.exists():
            os.replace(destination_path, backup)
        try:
            os.replace(build_root, destination_path)
        except Exception:
            if backup.exists() and not destination_path.exists():
                os.replace(backup, destination_path)
            raise
        if backup.exists():
            shutil.rmtree(backup)
        return verify_managed_skill_pack(destination_path)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def _safe_installed_path(root: Path, relative: str) -> Path:
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts:
        raise ManagedSkillPackViolation(f"unsafe installed skill path: {relative}")
    resolved = (root / rel).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ManagedSkillPackViolation(f"installed skill path escapes pack: {relative}") from exc
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise ManagedSkillPackViolation(f"symlinked installed skill path rejected: {relative}")
    return resolved


def verify_managed_skill_pack(root: str | Path) -> Dict[str, Any]:
    """Verify one installed managed pack and return frozen skill metadata/content."""
    root_path = Path(root).expanduser()
    if root_path.is_symlink() or not root_path.is_dir():
        raise ManagedSkillPackViolation(f"managed skill pack not found: {root_path}")
    try:
        manifest = json.loads((root_path / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManagedSkillPackViolation(f"invalid managed skill manifest: {exc}") from exc
    if manifest.get("schemaVersion") != _SCHEMA_VERSION:
        raise ManagedSkillPackViolation("unsupported managed skill manifest schema")
    verified: List[Dict[str, Any]] = []
    seen = set()
    for item in manifest.get("skills", []):
        name = str(item.get("name", ""))
        if not _SKILL_NAME.fullmatch(name) or name in seen:
            raise ManagedSkillPackViolation(f"invalid/duplicate managed skill name: {name!r}")
        seen.add(name)
        path = _safe_installed_path(root_path, str(item.get("path", "")))
        if not path.is_file():
            raise ManagedSkillPackViolation(f"managed skill file missing: {name}")
        content = path.read_text(encoding="utf-8")
        digest = "sha256:" + _sha256(content.encode("utf-8"))
        if digest != item.get("contentDigest"):
            raise ManagedSkillPackViolation(f"skill digest mismatch/tamper: {name}")
        tree_digest = "sha256:" + _tree_digest(path.parent)
        if tree_digest != item.get("treeDigest"):
            raise ManagedSkillPackViolation(f"skill tree digest mismatch/tamper: {name}")
        meta = _frontmatter(content)
        if str(meta.get("name", "")).strip().lower() != name:
            raise ManagedSkillPackViolation(f"managed skill name mismatch: {name}")
        if not str(meta.get("description", "")).strip():
            raise ManagedSkillPackViolation(f"managed skill description missing: {name}")
        copied = dict(item)
        copied["content"] = content
        copied["baseDir"] = str(path.parent.resolve())
        verified.append(copied)
    manifest_digest = _manifest_digest(manifest)
    return {
        "packName": str(manifest.get("packName", "")),
        "packVersion": str(manifest.get("packVersion", "")),
        "manifestDigest": manifest_digest,
        "sourceRoots": list(manifest.get("sourceRoots", [])),
        "trust": "managed_local",
        "skills": verified,
        "skillCount": len(verified),
    }


def default_managed_skill_root(state_root: str | Path, pack_name: str = "ultimate") -> Path:
    return Path(state_root).expanduser() / "skills" / pack_name


def _tokens(value: str) -> set[str]:
    return {t for t in _TOKEN.findall(value.lower()) if len(t) > 2 and t not in _STOPWORDS}


def _when_text(content: str) -> str:
    lines = content.splitlines()
    collecting = False
    parts: List[str] = []
    for line in lines:
        heading = re.match(r"^#{2,3}\s+(.+?)\s*$", line)
        if heading:
            title = heading.group(1).strip().lower()
            if collecting and title not in {"when to use", "when to apply"}:
                break
            collecting = title in {"when to use", "when to apply"}
            continue
        if collecting:
            parts.append(line)
    return " ".join(parts)


def _negative_tokens(content: str) -> set[str]:
    found: set[str] = set()
    for line in content.splitlines():
        low = line.lower()
        for marker in ("not for", "skip it for", "skip for", "do not use for"):
            if marker in low:
                found |= _tokens(low.split(marker, 1)[1])
    return found


def _heading_tokens(content: str) -> set[str]:
    return _tokens(" ".join(
        m.group(1) for line in content.splitlines()
        if (m := re.match(r"^#{1,3}\s+(.+?)\s*$", line))
    ))


def _imperative_trigger_tokens(description: str) -> set[str]:
    """Extract direct invocation words from descriptions like `user says proceed, continue`."""
    low = description.lower()
    marker = "user says"
    if marker not in low:
        return set()
    tail = low.split(marker, 1)[1].split(".", 1)[0]
    return _tokens(tail.replace("/", " "))


def select_managed_skills(
    objective: str, verified_pack: Mapping[str, Any], *, limit: int = 4
) -> List[str]:
    """Deterministically rank applicable managed skills for an objective."""
    if not isinstance(objective, str) or not objective.strip():
        return []
    limit = max(1, min(int(limit), 8))
    objective_lower = " ".join(objective.lower().split())
    objective_tokens = _tokens(objective_lower)
    ranked: List[tuple[int, str]] = []
    for item in verified_pack.get("skills", []):
        if not item.get("inlineable", True):
            continue
        name = str(item.get("name", ""))
        description = str(item.get("description", ""))
        content = str(item.get("content", ""))
        score = 0
        for trigger in item.get("triggers", []) or []:
            phrase = " ".join(str(trigger).lower().split())
            if phrase and phrase in objective_lower:
                score += 14
        name_overlap = len(objective_tokens & _tokens(name.replace("-", " ")))
        desc_overlap = len(objective_tokens & _tokens(description))
        when_overlap = len(objective_tokens & _tokens(_when_text(content)))
        heading_overlap = len(objective_tokens & _heading_tokens(content))
        score += name_overlap * 5 + desc_overlap * 2 + when_overlap * 2 + heading_overlap
        if description.lower().lstrip().startswith("use when") and desc_overlap:
            score += 4
        score += len(objective_tokens & _imperative_trigger_tokens(description)) * 10
        score -= len(objective_tokens & _negative_tokens(content)) * 6
        if score >= 6:
            ranked.append((score, name))
    ranked.sort(key=lambda pair: (-pair[0], pair[1]))
    return [name for _, name in ranked[:limit]]


def prepare_managed_skill_context(
    root: str | Path,
    objective: str,
    *,
    explicit_names: Sequence[str] | None = None,
    limit: int = 4,
) -> tuple[Dict[str, Any] | None, List[str]]:
    """Verify, select, and freeze managed skill text for one approval basis."""
    verified = verify_managed_skill_pack(root)
    by_name = {item["name"]: item for item in verified["skills"]}
    if explicit_names is not None:
        names: List[str] = []
        for raw in explicit_names:
            name = str(raw)
            if name not in by_name:
                raise ManagedSkillPackViolation(f"unknown managed skill requested: {name}")
            if name not in names:
                names.append(name)
        if len(names) > 8:
            raise ManagedSkillPackViolation("at most 8 managed skills may be selected")
    else:
        names = select_managed_skills(objective, verified, limit=limit)
    if not names:
        return None, []
    selected: List[Dict[str, str]] = []
    for name in names:
        item = by_name[name]
        if not item.get("inlineable", True) or len(item["content"]) > _INLINE_CONTENT_LIMIT:
            raise ManagedSkillPackViolation(
                f"skill too large for inline authored-skill context: {name}"
            )
        selected.append({
            "name": name,
            "version": str(item.get("version") or "0.0.0"),
            "contentDigest": str(item["contentDigest"]),
            "content": str(item["content"]),
        })
    digest_hex = str(verified["manifestDigest"]).split(":", 1)[1]
    context = {
        "packName": verified["packName"],
        "packVersion": verified["packVersion"],
        "sourceRepository": f"managed://local/{verified['packName']}",
        "sourceRef": "manifest-v1",
        "sourceCommit": digest_hex,
        "sourceTree": digest_hex,
        "manifestDigest": verified["manifestDigest"],
        "trust": "managed_local",
        "skills": selected,
    }
    return context, names
