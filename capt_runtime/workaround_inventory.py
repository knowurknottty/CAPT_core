"""Read-only inventory of ad-hoc Python tools near CAPT workspaces.

Evidence of repeated workarounds is NOT proof of a missing production feature.
This scanner never imports, executes, changes, or uploads inspected Python files.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any

CAPABILITY_MAP = {
    "council_launch": "native governed CouncilMission setup/dispatch",
    "approval_orchestration": "exact-scope ApprovalBundle",
    "provider_health": "provider/Prompt Intelligence diagnostics",
    "runtime_recovery": "supervised restart, bounded failover, migration",
    "mission_triage": "Mission/Task/DriverRun health projection",
    "desktop_acceptance": "semantic AX/UI acceptance harness",
    "code_patch": "governed file patch with CAS, rollback and tests",
    "ad_hoc_debug": "versioned and bounded diagnostic commands",
    "domain_research": "domain-specific research; not automatically a CAPT gap",
    "other": "manual review",
}
SKIP_DIRS = frozenset({
    ".git", ".venv", "venv", "site-packages", "__pycache__",
    "node_modules", ".worktrees", "build", "dist", ".mypy_cache", ".pytest_cache",
})


def category(name: str) -> str:
    """Explicit, deterministic triage labels; never assert a capability is missing."""
    n = name.lower().replace("-", "_")
    if any(v in n for v in ("council", "cohort", "vessel", "model_review", "dispatch")):
        return "council_launch"
    if any(v in n for v in ("approval", "authority", "capability")):
        return "approval_orchestration"
    if any(v in n for v in ("pi_probe", "pi_smoke", "prompt_intelligence", "model_probe")):
        return "provider_health"
    if any(v in n for v in ("hardening", "failover", "recovery", "migration", "restart")):
        return "runtime_recovery"
    if any(v in n for v in ("triage", "mission_health")):
        return "mission_triage"
    if any(v in n for v in ("swift", "tia", "ax_smoke", "bot_ui", "desktop_smoke")):
        return "desktop_acceptance"
    if any(v in n for v in ("fix", "patch", "workaround", "shim")):
        return "code_patch"
    if n.startswith(".tmp") or any(v in n for v in ("_debug", "_diagnostic")):
        return "ad_hoc_debug"
    if any(v in n for v in ("stage4", "stage9", "stage11", "astra44", "competition")):
        return "domain_research"
    return "other"


def inspect_script(path: Path) -> dict[str, Any]:
    """AST parse but NEVER execute. Return bounded metadata and source digest."""
    raw = path.read_bytes()
    value: dict[str, Any] = {
        "path": str(path), "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw), "category": category(path.name),
        "capabilityCandidate": CAPABILITY_MAP[category(path.name)],
    }
    try:
        tree = ast.parse(raw, filename=str(path))
    except (SyntaxError, UnicodeDecodeError, ValueError) as exc:
        value["parseStatus"] = "invalid"
        value["errorType"] = type(exc).__name__
        return value
    value["parseStatus"] = "valid"
    value["entryPoints"] = [
        node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ][:20]
    value["hasTopLevelStatements"] = any(
        isinstance(node, (ast.Expr, ast.Assign, ast.AugAssign, ast.AnnAssign, ast.With, ast.Try))
        for node in tree.body
    )
    value["usesShellOrNetwork"] = any(
        isinstance(node, ast.Import) and any(
            alias.name.split(".")[0] in {"subprocess", "socket", "urllib", "requests", "httpx"}
            for alias in node.names
        ) or isinstance(node, ast.ImportFrom) and (
            (node.module or "").split(".")[0] in {"subprocess", "socket", "urllib", "requests", "httpx"}
        )
        for node in ast.walk(tree)
    )
    return value


def inventory(roots: list[Path], max_files: int = 1000) -> dict[str, Any]:
    if isinstance(max_files, bool) or not 1 <= max_files <= 10000:
        raise ValueError("max_files must be in 1..10000")
    paths: set[Path] = set()
    for raw_root in roots:
        root = raw_root.expanduser().resolve(strict=True)
        if not root.is_dir():
            raise ValueError("root must be a directory: " + str(root))
        # Only direct scripts. Explicitly opt into deeper subprojects by adding roots.
        for p in root.glob("*.py"):
            if p.is_file() and not p.is_symlink() and p.parent.name not in SKIP_DIRS:
                paths.add(p)
    selected = sorted(paths, key=str)
    if len(selected) > max_files:
        raise ValueError("inventory scope exceeds max_files; refine roots")
    records = [inspect_script(p) for p in selected]
    counts: dict[str, int] = {}
    for row in records:
        counts[row["category"]] = counts.get(row["category"], 0) + 1
    return {
        "schemaVersion": "capt.workaround-inventory.1",
        "mode": "read_only_metadata",
        "scope": [str(p.expanduser().resolve()) for p in roots],
        "recordCount": len(records),
        "countsByCategory": dict(sorted(counts.items())),
        "notProofOfMissingFeatures": True,
        "scripts": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, action="append", required=True)
    parser.add_argument("--max-files", type=int, default=1000)
    args = parser.parse_args()
    print(json.dumps(inventory(args.root, max_files=args.max_files), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
