#!/usr/bin/env python3
"""Tree-sitter structural hashing probe (CAPT-UPG-022).

The hashes in this module represent normalized syntax-tree structure/content.
They are useful candidates for provenance and selective invalidation. They do
NOT prove behavioral or semantic equivalence of programs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


def _hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _node_children(node: Any) -> List[Any]:
    children = getattr(node, "children", None)
    return list(children or [])


def _is_named(node: Any) -> bool:
    return bool(getattr(node, "is_named", True))


def _leaf_text(node: Any, source: bytes) -> Optional[str]:
    children = [child for child in _node_children(node) if _is_named(child) and getattr(child, "type", "") != "comment"]
    if children:
        return None
    start = int(getattr(node, "start_byte", 0))
    end = int(getattr(node, "end_byte", start))
    try:
        return source[start:end].decode("utf-8")
    except UnicodeDecodeError:
        return source[start:end].decode("utf-8", errors="replace")


def normalize_tree(node: Any, source: bytes, *, include_leaf_text: bool = True) -> Dict[str, Any]:
    """Normalize a Tree-sitter-like node without source coordinates.

    Comments and anonymous punctuation/whitespace nodes are excluded. Named leaf
    text is retained by default so identifier/literal edits can invalidate the
    structural digest.
    """
    children = [
        normalize_tree(child, source, include_leaf_text=include_leaf_text)
        for child in _node_children(node)
        if _is_named(child) and getattr(child, "type", "") != "comment"
    ]
    result: Dict[str, Any] = {
        "type": str(getattr(node, "type", "unknown")),
        "children": children,
    }
    if include_leaf_text and not children:
        result["text"] = _leaf_text(node, source)
    return result


def hash_tree(root: Any, source: bytes, *, include_leaf_text: bool = True) -> Dict[str, Any]:
    normalized = normalize_tree(root, source, include_leaf_text=include_leaf_text)
    subtrees: List[Dict[str, Any]] = []

    def walk(node: Any, path: Tuple[int, ...]) -> None:
        if _is_named(node) and getattr(node, "type", "") != "comment":
            norm = normalize_tree(node, source, include_leaf_text=include_leaf_text)
            subtrees.append({
                "path": list(path),
                "type": str(getattr(node, "type", "unknown")),
                "digest": _hash(norm),
            })
        named_children = [
            child for child in _node_children(node)
            if _is_named(child) and getattr(child, "type", "") != "comment"
        ]
        for index, child in enumerate(named_children):
            walk(child, path + (index,))

    walk(root, ())
    return {
        "schemaVersion": "1.0.0",
        "kind": "TreeSitterStructuralHash",
        "rootDigest": _hash(normalized),
        "normalizedTree": normalized,
        "subtrees": subtrees,
        "coordinateSensitive": False,
        "commentsIncluded": False,
        "leafTextIncluded": include_leaf_text,
        "behavioralEquivalenceClaim": False,
        "semanticEquivalenceClaim": False,
    }


def hash_source_with_tree_sitter(source: bytes, language: str) -> Dict[str, Any]:
    """Use an optional Tree-sitter language-pack adapter when available."""
    try:
        from tree_sitter_language_pack import get_parser  # type: ignore
    except Exception as exc:  # noqa: BLE001
        return {
            "schemaVersion": "1.0.0",
            "kind": "TreeSitterStructuralHashProbe",
            "status": "dependency_unavailable",
            "language": language,
            "dependency": "tree_sitter_language_pack",
            "detail": type(exc).__name__,
            "behavioralEquivalenceClaim": False,
            "semanticEquivalenceClaim": False,
        }
    try:
        parser = get_parser(language)
        tree = parser.parse(source)
    except Exception as exc:  # noqa: BLE001
        return {
            "schemaVersion": "1.0.0",
            "kind": "TreeSitterStructuralHashProbe",
            "status": "parse_unavailable",
            "language": language,
            "detail": type(exc).__name__,
            "behavioralEquivalenceClaim": False,
            "semanticEquivalenceClaim": False,
        }
    result = hash_tree(tree.root_node, source)
    result["status"] = "ok"
    result["language"] = language
    return result


def compare_hashes(before: Mapping[str, Any], after: Mapping[str, Any]) -> Dict[str, Any]:
    before_map = {tuple(item["path"]): item["digest"] for item in before.get("subtrees", []) or []}
    after_map = {tuple(item["path"]): item["digest"] for item in after.get("subtrees", []) or []}
    paths = sorted(set(before_map).union(after_map))
    changed = [list(path) for path in paths if before_map.get(path) != after_map.get(path)]
    unchanged = [list(path) for path in paths if before_map.get(path) == after_map.get(path)]
    return {
        "rootChanged": before.get("rootDigest") != after.get("rootDigest"),
        "changedSubtreePaths": changed,
        "unchangedSubtreePaths": unchanged,
        "behavioralEquivalenceClaim": False,
        "semanticEquivalenceClaim": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="CAPT Tree-sitter structural hashing probe")
    parser.add_argument("path", type=Path)
    parser.add_argument("--language", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = hash_source_with_tree_sitter(args.path.read_bytes(), args.language)
    text = json.dumps(result, sort_keys=True, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result.get("status") == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
