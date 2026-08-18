"""Bounded read-only Forge advisory engine.

This module adopts the useful archaeology/gap/brief concepts from the legacy
Forge donor without importing its BaseModule runtime, direct writes, or
claims of authoritative implementation decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Mapping, Tuple

from capt_lab.contracts import LabEngineRequest, LabEngineResult, LabInputError

_ENGINE_ID = "lab.forge"
_ENGINE_VERSION = "0.1.0"

_IGNORED_DIRS = frozenset({
    ".git", ".hg", ".svn", "node_modules", "target", "build", "dist",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv", "venv",
})
_SECRET_NAMES = frozenset({
    ".env", ".env.local", ".env.development", ".env.production", ".env.test",
    "id_rsa", "id_ed25519", "credentials", "credentials.json", "secrets.json",
})
_SECRET_SUFFIXES = frozenset({".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"})
_BINARY_SUFFIXES = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz",
    ".tar", ".7z", ".dmg", ".pkg", ".so", ".dylib", ".dll", ".exe", ".bin",
    ".class", ".pyc", ".o", ".a", ".wasm", ".sqlite", ".db",
})
_SECRET_CONTENT_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)(?:api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_\-/.+=]{12,}"),
    re.compile(r"\b(?:ghp_|github_pat_)[A-Za-z0-9_]{12,}"),
)
_DIMENSIONS = ("Precision", "Reusability", "Safety", "Auditability", "Effectiveness")
_REQUIRED_NOTES = ("Assumptions", "Known limits", "Experimental elements", "Confidence tag")


@dataclass(frozen=True)
class ForgeLimits:
    max_files: int = 512
    max_total_bytes: int = 2 * 1024 * 1024
    max_depth: int = 8
    max_file_bytes: int = 64 * 1024

    def __post_init__(self) -> None:
        bounds = {
            "max_files": (self.max_files, 1, 4096),
            "max_total_bytes": (self.max_total_bytes, 1, 16 * 1024 * 1024),
            "max_depth": (self.max_depth, 1, 32),
            "max_file_bytes": (self.max_file_bytes, 1, 1024 * 1024),
        }
        for name, (value, low, high) in bounds.items():
            if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
                raise LabInputError("%s must be an integer in [%d, %d]" % (name, low, high))


@dataclass
class _Scan:
    root: Path
    files: List[Dict[str, Any]]
    texts: Dict[str, str]
    excluded: List[str]
    bytes_read: int
    truncated: bool


def _validate_root(root: Path) -> Path:
    raw = Path(root).expanduser()
    if not raw.is_absolute():
        raise LabInputError("Forge root must be an absolute canonical path")
    if ".." in raw.parts or "." in raw.parts:
        raise LabInputError("Forge root must be canonical and contain no traversal components")
    if raw.is_symlink():
        raise LabInputError("Forge root may not be a symlink")
    if not raw.exists() or not raw.is_dir():
        raise LabInputError("Forge root must be an existing directory")
    resolved = raw.resolve(strict=True)
    if str(raw) != str(resolved):
        raise LabInputError("Forge root must already be canonical")
    return resolved


def _relative(candidate: Path, root: Path) -> str:
    return candidate.relative_to(root).as_posix()


def _inside(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def _secret_name(path: Path) -> bool:
    name = path.name.lower()
    if name in _SECRET_NAMES or name.startswith(".env."):
        return True
    return path.suffix.lower() in _SECRET_SUFFIXES


def _looks_binary(path: Path, sample: bytes) -> bool:
    if path.suffix.lower() in _BINARY_SUFFIXES:
        return True
    if b"\x00" in sample:
        return True
    if not sample:
        return False
    controls = sum(1 for b in sample if b < 9 or (13 < b < 32))
    return controls / len(sample) > 0.08


def _contains_secret(text: str) -> bool:
    return any(pattern.search(text) for pattern in _SECRET_CONTENT_PATTERNS)


def _language(path: Path) -> str:
    return {
        ".py": "python", ".rs": "rust", ".swift": "swift", ".ts": "typescript",
        ".tsx": "typescript", ".js": "javascript", ".jsx": "javascript", ".go": "go",
        ".java": "java", ".kt": "kotlin", ".c": "c", ".h": "c-header", ".cpp": "cpp",
        ".md": "markdown", ".txt": "text", ".toml": "toml", ".json": "json",
        ".yaml": "yaml", ".yml": "yaml", ".sh": "shell", ".zsh": "shell",
    }.get(path.suffix.lower(), "other")


def _scan_repository(root: Path, limits: ForgeLimits) -> _Scan:
    canonical = _validate_root(root)
    files: List[Dict[str, Any]] = []
    texts: Dict[str, str] = {}
    excluded = set()
    bytes_read = 0
    truncated = False

    for current, dirs, names in os.walk(canonical, topdown=True, followlinks=False):
        current_path = Path(current)
        rel_current = current_path.relative_to(canonical)
        depth = len(rel_current.parts)
        kept_dirs = []
        for dirname in sorted(dirs):
            child = current_path / dirname
            rel = _relative(child, canonical)
            if dirname in _IGNORED_DIRS:
                excluded.add(dirname if depth == 0 else rel)
                continue
            if child.is_symlink():
                excluded.add(rel)
                continue
            try:
                resolved = child.resolve(strict=True)
            except (OSError, RuntimeError):
                excluded.add(rel)
                continue
            if not _inside(resolved, canonical):
                excluded.add(rel)
                continue
            if depth + 1 > limits.max_depth:
                excluded.add(rel)
                truncated = True
                continue
            kept_dirs.append(dirname)
        dirs[:] = kept_dirs

        for name in sorted(names):
            path = current_path / name
            rel = _relative(path, canonical)
            if len(path.relative_to(canonical).parts) - 1 > limits.max_depth:
                excluded.add(rel)
                truncated = True
                continue
            if len(files) >= limits.max_files:
                excluded.add(rel)
                truncated = True
                continue
            if path.is_symlink():
                excluded.add(rel)
                continue
            if _secret_name(path):
                excluded.add(rel)
                continue
            try:
                resolved = path.resolve(strict=True)
                stat = path.stat()
            except (OSError, RuntimeError):
                excluded.add(rel)
                continue
            if not _inside(resolved, canonical) or not path.is_file():
                excluded.add(rel)
                continue
            if stat.st_size > limits.max_file_bytes:
                excluded.add(rel)
                truncated = True
                continue
            if bytes_read + stat.st_size > limits.max_total_bytes:
                excluded.add(rel)
                truncated = True
                continue
            try:
                data = path.read_bytes()
            except OSError:
                excluded.add(rel)
                continue
            if _looks_binary(path, data[:4096]):
                excluded.add(rel)
                continue
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                excluded.add(rel)
                continue
            if _contains_secret(text):
                excluded.add(rel)
                continue
            bytes_read += len(data)
            digest = "sha256:" + hashlib.sha256(data).hexdigest()
            files.append({
                "path": rel,
                "bytes": len(data),
                "sha256": digest,
                "language": _language(path),
            })
            texts[rel] = text

    files.sort(key=lambda item: item["path"])
    return _Scan(
        root=canonical,
        files=files,
        texts=texts,
        excluded=sorted(excluded),
        bytes_read=bytes_read,
        truncated=truncated,
    )


def _public_scan(scan: _Scan) -> Dict[str, Any]:
    languages: Dict[str, int] = {}
    for item in scan.files:
        languages[item["language"]] = languages.get(item["language"], 0) + 1
    return {
        "fileCount": len(scan.files),
        "bytesRead": scan.bytes_read,
        "files": [item["path"] for item in scan.files],
        "fileMetadata": scan.files,
        "languages": {key: languages[key] for key in sorted(languages)},
        "excluded": scan.excluded,
        "truncated": scan.truncated,
    }


def analyze_repository(root: Path, limits: ForgeLimits = ForgeLimits()) -> Dict[str, Any]:
    return _public_scan(_scan_repository(Path(root), limits))


def _limits_from(raw: Any) -> ForgeLimits:
    if raw is None:
        return ForgeLimits()
    if not isinstance(raw, dict):
        raise LabInputError("limits must be an object")
    allowed = {"maxFiles", "maxTotalBytes", "maxDepth", "maxFileBytes"}
    unknown = set(raw) - allowed
    if unknown:
        raise LabInputError("unknown limits field(s): %s" % ", ".join(sorted(unknown)))
    return ForgeLimits(
        max_files=raw.get("maxFiles", 512),
        max_total_bytes=raw.get("maxTotalBytes", 2 * 1024 * 1024),
        max_depth=raw.get("maxDepth", 8),
        max_file_bytes=raw.get("maxFileBytes", 64 * 1024),
    )


def _bounded_text(label: str, value: Any, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise LabInputError("%s must be a non-empty string <= %d chars" % (label, maximum))
    return value.strip()


def _root_value(value: Mapping[str, Any]) -> Path:
    root = value.get("root")
    if not isinstance(root, str) or not root:
        raise LabInputError("root must be a non-empty absolute path string")
    return Path(root)


def _expectations(raw: Any) -> List[str]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= 128:
        raise LabInputError("expectations must contain 1..128 strings")
    values = [_bounded_text("expectation", item, 1024) for item in raw]
    return sorted(set(values), key=lambda x: x.lower())


def _tokens(text: str) -> List[str]:
    return [token for token in re.findall(r"[A-Za-z0-9_]+", text.lower()) if len(token) > 2]


def _gap_entries(scan: _Scan, expectations: List[str]) -> List[Dict[str, Any]]:
    corpus = "\n".join(scan.texts[path] for path in sorted(scan.texts)).lower()
    entries = []
    for expectation in expectations:
        phrase = expectation.lower()
        phrase_found = phrase in corpus
        tokens = _tokens(expectation)
        token_hits = sum(1 for token in set(tokens) if token in corpus)
        coverage = token_hits / len(set(tokens)) if tokens else 0.0
        observed_paths = [
            path for path, text in sorted(scan.texts.items())
            if phrase in text.lower() or (tokens and all(token in text.lower() for token in set(tokens)))
        ][:16]
        entries.append({
            "expectation": expectation,
            "status": "text_match_found" if phrase_found else "not_observed",
            "tokenCoverage": coverage,
            "observedPaths": observed_paths,
        })
    return sorted(entries, key=lambda item: item["expectation"].lower())


def _repository_result(value: Mapping[str, Any]) -> LabEngineResult:
    allowed = {"root", "limits"}
    unknown = set(value) - allowed
    if unknown:
        raise LabInputError("unknown input field(s): %s" % ", ".join(sorted(unknown)))
    scan = _scan_repository(_root_value(value), _limits_from(value.get("limits")))
    return LabEngineResult(
        engine_id=_ENGINE_ID,
        engine_version=_ENGINE_VERSION,
        operation="repository_archaeology",
        epistemic_class="advisory",
        observation=_public_scan(scan),
        limitations=(
            "Repository archaeology is bounded read-only observation; omitted files may contain relevant information.",
            "A textual file match does not establish correctness, implementation completeness, or verification.",
        ),
    )


def _gap_result(value: Mapping[str, Any]) -> LabEngineResult:
    allowed = {"root", "expectations", "limits"}
    unknown = set(value) - allowed
    if unknown:
        raise LabInputError("unknown input field(s): %s" % ", ".join(sorted(unknown)))
    expectations = _expectations(value.get("expectations"))
    scan = _scan_repository(_root_value(value), _limits_from(value.get("limits")))
    gaps = _gap_entries(scan, expectations)
    return LabEngineResult(
        engine_id=_ENGINE_ID,
        engine_version=_ENGINE_VERSION,
        operation="gap_analysis",
        epistemic_class="advisory",
        observation={
            "repository": _public_scan(scan),
            "gaps": gaps,
            "notObservedCount": sum(item["status"] == "not_observed" for item in gaps),
        },
        limitations=(
            "not_observed means the bounded textual scan did not observe the expectation; it does not prove absence.",
            "text_match_found is evidence of text presence only and does not prove implementation.",
        ),
    )


def _sigma_result(value: Mapping[str, Any]) -> LabEngineResult:
    allowed = {"root", "objective", "expectations", "limits"}
    unknown = set(value) - allowed
    if unknown:
        raise LabInputError("unknown input field(s): %s" % ", ".join(sorted(unknown)))
    objective = _bounded_text("objective", value.get("objective"), 2048)
    expectations = _expectations(value.get("expectations"))
    scan = _scan_repository(_root_value(value), _limits_from(value.get("limits")))
    gaps = _gap_entries(scan, expectations)
    lines = [
        "# SIGMA IMPLEMENTATION BRIEF",
        "",
        "## OBJECTIVE",
        objective,
        "",
        "## BOUNDED REPOSITORY OBSERVATION",
        "Files admitted: %d" % len(scan.files),
        "Bytes read: %d" % scan.bytes_read,
        "Scan truncated: %s" % ("yes" if scan.truncated else "no"),
        "Languages: %s" % (", ".join("%s=%d" % item for item in sorted(_public_scan(scan)["languages"].items())) or "none"),
        "",
        "## EXPECTATION REGISTER",
    ]
    for index, item in enumerate(gaps, 1):
        lines.append("- G%03d [%s] %s" % (index, item["status"].upper(), item["expectation"]))
    lines.extend([
        "",
        "## EXECUTION DIRECTIVE",
        "Treat this brief as an advisory implementation input. Inspect authoritative CAPT evidence and project contracts before mutation.",
        "For each NOT_OBSERVED item, determine whether it is truly absent before implementing anything.",
        "Do not infer task completion, verification, novelty, patentability, or owner approval from this brief.",
    ])
    return LabEngineResult(
        engine_id=_ENGINE_ID,
        engine_version=_ENGINE_VERSION,
        operation="sigma_brief",
        epistemic_class="advisory",
        observation={"brief": "\n".join(lines), "gapCount": len(gaps)},
        limitations=(
            "The brief is generated from a bounded read-only scan and operator-supplied expectations.",
            "It is not an approval, verification result, patent analysis, or authoritative implementation plan.",
        ),
    )


def _forgeproof_result(value: Mapping[str, Any]) -> LabEngineResult:
    if set(value) != {"scores", "notes"}:
        raise LabInputError("forgeproof_score requires exactly scores and notes")
    scores = value["scores"]
    notes = value["notes"]
    if not isinstance(scores, dict) or set(scores) != set(_DIMENSIONS):
        raise LabInputError("scores must contain exactly: %s" % ", ".join(_DIMENSIONS))
    if not isinstance(notes, dict) or set(notes) != set(_REQUIRED_NOTES):
        raise LabInputError("notes must contain exactly: %s" % ", ".join(_REQUIRED_NOTES))
    normalized: Dict[str, float] = {}
    for name in _DIMENSIONS:
        raw = scores[name]
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise LabInputError("score %s must be numeric" % name)
        score = float(raw)
        if not math_isfinite(score) or not 0.0 <= score <= 5.0:
            raise LabInputError("score %s must be in [0, 5]" % name)
        normalized[name] = score
    normalized_notes = {name: _bounded_text("notes.%s" % name, notes[name], 2048) for name in _REQUIRED_NOTES}
    average = sum(normalized.values()) / len(normalized)
    weak = [name for name in _DIMENSIONS if normalized[name] < 4.0]
    return LabEngineResult(
        engine_id=_ENGINE_ID,
        engine_version=_ENGINE_VERSION,
        operation="forgeproof_score",
        epistemic_class="advisory",
        observation={
            "scores": normalized,
            "averageScore": average,
            "weakDimensions": weak,
            "meetsThreshold": not weak and average >= 4.0,
            "acceptanceThreshold": 4.0,
            "scoreSource": "operator_supplied",
            "notes": normalized_notes,
        },
        limitations=(
            "ForgeProof scores are operator-supplied rubric inputs; CAPT does not fabricate an independent reviewer.",
            "Meeting the rubric threshold is advisory and does not constitute CAPT verification or approval.",
        ),
    )


def math_isfinite(value: float) -> bool:
    # Kept local to avoid importing numerical packages into the Forge path.
    return value == value and value not in (float("inf"), float("-inf"))


def execute_forge(request: LabEngineRequest, context: Mapping[str, Any]) -> LabEngineResult:
    if request.engine_id != _ENGINE_ID:
        raise LabInputError("Forge adapter received wrong engineId")
    if request.operation == "repository_archaeology":
        return _repository_result(request.input)
    if request.operation == "gap_analysis":
        return _gap_result(request.input)
    if request.operation == "sigma_brief":
        return _sigma_result(request.input)
    if request.operation == "forgeproof_score":
        return _forgeproof_result(request.input)
    raise LabInputError("unsupported Forge operation %s" % request.operation)
