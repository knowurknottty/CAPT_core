"""Bounded read-only repository intelligence for FORGE/SIGMA prompt stages.

This is a Core port of the proven Inversion Labs Forge observation semantics.
It performs no writes, grants no capabilities, and all outputs remain advisory.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Mapping

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
                raise ValueError("%s must be an integer in [%d, %d]" % (name, low, high))


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
        raise ValueError("Forge root must be an absolute canonical path")
    if ".." in raw.parts or "." in raw.parts:
        raise ValueError("Forge root must be canonical and contain no traversal components")
    if raw.is_symlink():
        raise ValueError("Forge root may not be a symlink")
    if not raw.exists() or not raw.is_dir():
        raise ValueError("Forge root must be an existing directory")
    resolved = raw.resolve(strict=True)
    if str(raw) != str(resolved):
        raise ValueError("Forge root must already be canonical")
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
        raise ValueError("limits must be an object")
    allowed = {"maxFiles", "maxTotalBytes", "maxDepth", "maxFileBytes"}
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError("unknown limits field(s): %s" % ", ".join(sorted(unknown)))
    return ForgeLimits(
        max_files=raw.get("maxFiles", 512),
        max_total_bytes=raw.get("maxTotalBytes", 2 * 1024 * 1024),
        max_depth=raw.get("maxDepth", 8),
        max_file_bytes=raw.get("maxFileBytes", 64 * 1024),
    )


def _bounded_text(label: str, value: Any, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError("%s must be a non-empty string <= %d chars" % (label, maximum))
    return value.strip()


def _root_value(value: Mapping[str, Any]) -> Path:
    root = value.get("root")
    if not isinstance(root, str) or not root:
        raise ValueError("root must be a non-empty absolute path string")
    return Path(root)


def _expectations(raw: Any) -> List[str]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= 128:
        raise ValueError("expectations must contain 1..128 strings")
    values = [_bounded_text("expectation", item, 1024) for item in raw]
    return sorted(set(values), key=lambda x: x.lower())


_LEXICAL_STOPWORDS = frozenset({
    "and", "are", "but", "for", "from", "had", "has", "have", "into", "its",
    "that", "the", "their", "then", "these", "this", "those", "was", "were",
    "will", "with", "would",
})


def _tokens(text: str) -> List[str]:
    return [
        token for token in re.findall(r"[A-Za-z0-9_]+", text.lower())
        if len(token) > 2 and token not in _LEXICAL_STOPWORDS
    ]


def _token_forms(token: str) -> set[str]:
    forms = {token}
    # Avoid tiny lexical collisions such as new/news. Inflection matching is
    # advisory and deliberately conservative rather than a stemming engine.
    if len(token) >= 4:
        if token.endswith(("s", "x", "z", "ch", "sh")):
            forms.add(f"{token}es")
        else:
            forms.add(f"{token}s")
    if token.endswith("es") and len(token) > 5:
        forms.add(token[:-2])
    if token.endswith("s") and not token.endswith("ss") and len(token) > 4:
        forms.add(token[:-1])
    return forms


def _token_observed(token: str, observed: set[str]) -> bool:
    # Keep lexical matching conservative: only whole-token identity and simple
    # s/es inflections are related; arbitrary substrings remain non-matches.
    return bool(_token_forms(token) & observed)


def _gap_entries(scan: _Scan, expectations: List[str]) -> List[Dict[str, Any]]:
    corpus = "\n".join(scan.texts[path] for path in sorted(scan.texts)).lower()
    corpus_tokens = set(_tokens(corpus))
    path_tokens = {path: set(_tokens(text)) for path, text in scan.texts.items()}
    entries = []
    for expectation in expectations:
        phrase = expectation.lower()
        phrase_found = phrase in corpus
        tokens = set(_tokens(expectation))
        token_hits = sum(1 for token in tokens if _token_observed(token, corpus_tokens))
        coverage = token_hits / len(tokens) if tokens else 0.0
        observed_paths = [
            path for path, text in sorted(scan.texts.items())
            if phrase in text.lower()
            or (tokens and all(_token_observed(token, path_tokens[path]) for token in tokens))
        ][:16]
        if phrase_found:
            status = "text_match_found"
        elif observed_paths:
            status = "related_text_found"
        elif coverage > 0.0:
            status = "partial_text_evidence"
        else:
            status = "not_observed"
        entries.append({
            "expectation": expectation,
            "status": status,
            "tokenCoverage": coverage,
            "observedPaths": observed_paths,
        })
    return sorted(entries, key=lambda item: item["expectation"].lower())



def gap_analysis(root: Path, expectations: List[str], limits: ForgeLimits = ForgeLimits()) -> Dict[str, Any]:
    scan = _scan_repository(Path(root), limits)
    gaps = _gap_entries(scan, _expectations(expectations))
    return {
        "repository": _public_scan(scan),
        "gaps": gaps,
        "notObservedCount": sum(item["status"] == "not_observed" for item in gaps),
        "epistemicClass": "advisory",
        "limitations": [
            "not_observed means the bounded textual scan observed no expectation signal tokens; it does not prove absence.",
            "Lexical evidence does not prove implementation, correctness, completeness, or verification.",
        ],
    }


def sigma_brief(root: Path, objective: str, expectations: List[str], limits: ForgeLimits = ForgeLimits()) -> Dict[str, Any]:
    objective = _bounded_text("objective", objective, 2048)
    scan = _scan_repository(Path(root), limits)
    gaps = _gap_entries(scan, _expectations(expectations))
    public = _public_scan(scan)
    lines = [
        "# SIGMA IMPLEMENTATION BRIEF", "", "## OBJECTIVE", objective, "",
        "## BOUNDED REPOSITORY OBSERVATION",
        f"Files admitted: {len(scan.files)}", f"Bytes read: {scan.bytes_read}",
        f"Scan truncated: {'yes' if scan.truncated else 'no'}",
        "Languages: " + (", ".join(f"{k}={v}" for k, v in sorted(public["languages"].items())) or "none"),
        "", "## EXPECTATION REGISTER",
    ]
    for index, item in enumerate(gaps, 1):
        lines.append(f"- G{index:03d} [{item['status'].upper()}] {item['expectation']}")
    lines.extend([
        "", "## EXECUTION DIRECTIVE",
        "Treat this brief as advisory implementation input. Inspect authoritative CAPT evidence and project contracts before mutation.",
        "For each NOT_OBSERVED item, determine whether it is truly absent before implementing anything.",
        "Do not infer task completion, verification, novelty, patentability, or owner approval from this brief.",
    ])
    return {
        "brief": "\n".join(lines),
        "gaps": gaps,
        "repository": public,
        "epistemicClass": "advisory",
        "limitations": [
            "The brief is generated from a bounded read-only scan and supplied expectations.",
            "It is not an approval, verification result, patent analysis, or authoritative implementation plan.",
        ],
    }


def stage_repository_context(root: str, objective: str, expectations: List[str]) -> Dict[str, Any]:
    if not root:
        return {
            "repository": {"fileCount": 0, "bytesRead": 0, "files": [], "fileMetadata": [], "languages": {}, "excluded": [], "truncated": False},
            "gaps": [], "epistemicClass": "advisory",
            "limitations": ["No target root was approved, so repository observation was not performed."],
        }
    result = gap_analysis(Path(root), expectations or [objective])
    return result
