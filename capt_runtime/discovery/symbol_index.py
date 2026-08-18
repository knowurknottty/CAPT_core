"""Sparse symbol index over SEAL-admitted discovery candidates (CAPT-UPG-021).

Discovery remains the file-admission authority for this subsystem. This module
is a read-only derived index: it only consumes accepted file candidates from a
Discovery/SEAL result and never discovers or authorizes additional paths.
"""
from __future__ import annotations

import ast
import hashlib
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from capt_runtime.contracts import digest

INDEX_SCHEMA_VERSION = "1.0.0"


def _sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _safe_under_root(path: Path, root: Path) -> bool:
    try:
        resolved = path.resolve(strict=False)
        resolved_root = root.resolve(strict=False)
    except (OSError, RuntimeError):
        return False
    return resolved == resolved_root or str(resolved).startswith(str(resolved_root) + os.sep)


def _symbol_id(relative_path: str, qualname: str, line_start: int) -> str:
    return digest({"path": relative_path, "qualname": qualname, "lineStart": line_start})


class _SymbolVisitor(ast.NodeVisitor):
    def __init__(self, relative_path: str, source_lines: Sequence[str]) -> None:
        self.relative_path = relative_path
        self.source_lines = source_lines
        self.scope: List[str] = []
        self.symbols: List[Dict[str, Any]] = []

    def _record(self, node: Any, kind: str) -> None:
        name = str(node.name)
        qualname = ".".join(self.scope + [name])
        line_start = int(getattr(node, "lineno", 1))
        line_end = int(getattr(node, "end_lineno", line_start))
        line_end = max(line_start, min(line_end, len(self.source_lines)))
        snippet = "".join(self.source_lines[line_start - 1:line_end])
        self.symbols.append(
            {
                "symbolId": _symbol_id(self.relative_path, qualname, line_start),
                "path": self.relative_path,
                "name": name,
                "qualname": qualname,
                "kind": kind,
                "lineStart": line_start,
                "lineEnd": line_end,
                "byteLength": len(snippet.encode("utf-8")),
                "contentDigest": _sha256_text(snippet),
                "docstring": ast.get_docstring(node, clean=False),
            }
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        self._record(node, "class")
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._record(node, "function" if not self.scope else "method")
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._record(node, "async_function" if not self.scope else "async_method")
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()


def build_symbol_index(discovery: Mapping[str, Any]) -> Dict[str, Any]:
    """Index Python symbols from accepted SEAL candidates only."""
    root_raw = discovery.get("root")
    if not root_raw:
        raise ValueError("discovery result missing root")
    root = Path(str(root_raw)).expanduser()

    files: List[Dict[str, Any]] = []
    symbols: List[Dict[str, Any]] = []
    unsupported: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []
    admitted_count = 0
    total_source_bytes = 0

    for candidate in discovery.get("candidates", []) or []:
        if not candidate.get("accepted") or candidate.get("kind") != "file":
            continue
        admitted_count += 1
        raw_path = candidate.get("resolved_path") or candidate.get("path")
        if not raw_path:
            failures.append({"candidateId": candidate.get("candidate_id"), "reason": "missing_path"})
            continue
        path = Path(str(raw_path)).expanduser()
        if not _safe_under_root(path, root):
            failures.append({"path": str(path), "reason": "path_outside_discovery_root"})
            continue
        if path.suffix.lower() != ".py":
            unsupported.append({"path": str(path), "reason": "unsupported_language", "suffix": path.suffix.lower()})
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            failures.append({"path": str(path), "reason": "read_failed", "detail": type(exc).__name__})
            continue
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            failures.append({"path": str(path), "reason": "parse_failed", "line": exc.lineno})
            continue

        relative = os.path.relpath(str(path.resolve(strict=False)), str(root.resolve(strict=False)))
        source_bytes = len(text.encode("utf-8"))
        total_source_bytes += source_bytes
        visitor = _SymbolVisitor(relative, text.splitlines(True))
        visitor.visit(tree)
        file_symbols = visitor.symbols
        symbols.extend(file_symbols)
        files.append(
            {
                "path": relative,
                "sourceDigest": _sha256_text(text),
                "sourceBytes": source_bytes,
                "symbolCount": len(file_symbols),
                "candidateId": candidate.get("candidate_id"),
            }
        )

    result = {
        "schemaVersion": INDEX_SCHEMA_VERSION,
        "kind": "DiscoverySparseSymbolIndex",
        "authority": "derived_read_only",
        "discoveryRoot": str(root),
        "discoveryClassification": discovery.get("classification"),
        "coverage": {
            "admittedFileCandidates": admitted_count,
            "indexedFiles": len(files),
            "indexedSymbols": len(symbols),
            "unsupportedFiles": len(unsupported),
            "parseOrReadFailures": len(failures),
            "indexedSourceBytes": total_source_bytes,
        },
        "files": sorted(files, key=lambda x: x["path"]),
        "symbols": sorted(symbols, key=lambda x: (x["path"], x["lineStart"], x["qualname"])),
        "unsupported": sorted(unsupported, key=lambda x: x.get("path", "")),
        "failures": sorted(failures, key=lambda x: x.get("path", "")),
    }
    result["indexDigest"] = digest(result)
    return result


def select_symbols(index: Mapping[str, Any], query_terms: Iterable[str], max_symbols: int = 20) -> Dict[str, Any]:
    """Simple transparent lexical selector for the probe; no hidden relevance claim."""
    terms = [str(term).lower() for term in query_terms if str(term).strip()]
    scored: List[Tuple[int, str, Dict[str, Any]]] = []
    for symbol in index.get("symbols", []) or []:
        haystack = "%s %s %s %s" % (
            symbol.get("name", ""), symbol.get("qualname", ""),
            symbol.get("path", ""), symbol.get("docstring") or "",
        )
        lowered = haystack.lower()
        score = sum(1 for term in terms if term in lowered)
        if score > 0:
            scored.append((-score, str(symbol["symbolId"]), dict(symbol)))
    scored.sort()
    selected = [item[2] for item in scored[:max_symbols]]
    selected_ids = {item["symbolId"] for item in selected}
    omitted = [dict(symbol) for symbol in index.get("symbols", []) or [] if symbol.get("symbolId") not in selected_ids]
    return {
        "queryTerms": terms,
        "selected": selected,
        "omitted": omitted,
        "selectedCount": len(selected),
        "omittedCount": len(omitted),
        "selector": "transparent_lexical_probe",
        "sufficiencyClaim": False,
    }


def sparse_selection_metrics(
    index: Mapping[str, Any],
    selection: Mapping[str, Any],
    relevant_symbol_ids: Iterable[str],
) -> Dict[str, Any]:
    relevant: Set[str] = set(str(x) for x in relevant_symbol_ids)
    selected: Set[str] = set(str(x.get("symbolId")) for x in selection.get("selected", []) or [])
    tp = len(selected.intersection(relevant))
    fp = len(selected.difference(relevant))
    fn = len(relevant.difference(selected))
    precision = 0.0 if tp + fp == 0 else float(tp) / float(tp + fp)
    recall = 0.0 if tp + fn == 0 else float(tp) / float(tp + fn)
    selected_bytes = sum(int(x.get("byteLength") or 0) for x in selection.get("selected", []) or [])
    total_bytes = int((index.get("coverage") or {}).get("indexedSourceBytes") or 0)
    return {
        "truePositiveSymbols": tp,
        "falsePositiveSymbols": fp,
        "falseNegativeSymbols": fn,
        "precision": precision,
        "recall": recall,
        "selectedSymbolBytes": selected_bytes,
        "indexedSourceBytes": total_bytes,
        "byteReductionRatio": 0.0 if total_bytes == 0 else 1.0 - (float(selected_bytes) / float(total_bytes)),
        "contextSufficiencyProven": False,
    }
