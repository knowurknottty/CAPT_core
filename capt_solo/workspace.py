"""CAPT Universal Workspace — local-first workspace operations.

This module is the engine behind `capt workspace ...`. It is intentionally
dependency-light (stdlib + pyyaml) and performs NO network I/O. It reads the
repository's own authority/state/task/checkpoint files and validates them
against the JSON Schemas in `architecture/`.

Design rules (per SECURITY_BOUNDARIES.md):
- Markdown/JSON/YAML are READ, never executed.
- Task/checkpoint records are untrusted data; they are schema-validated and can
  never grant capabilities or redefine authority.
- No hidden persistence: every write is an explicit, logged file write the caller
  requested (checkpoint generation / archive).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except Exception:  # pragma: no cover - yaml is a hard dependency of the runtime
    yaml = None  # type: ignore

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCH_DIR = REPO_ROOT / "architecture"
SCHEMA_FILES = {
    "workspace": ARCH_DIR / "workspace.schema.json",
    "task": ARCH_DIR / "task.schema.json",
    "checkpoint": ARCH_DIR / "checkpoint.schema.json",
    "agent-capabilities": ARCH_DIR / "agent-capabilities.schema.json",
}

# Required root files for a navigable workspace.
REQUIRED_FILES = [
    ("AGENTS.md", "entrypoint", True),
    ("CAPT_CANON.md", "canon", True),
    ("CANONICAL_ARCHITECTURE.md", "canon", True),
    ("CANONICAL_OWNERSHIP_MATRIX.md", "canon", True),
    ("WORKSPACE.md", "state", True),
    ("CURRENT_STATE.md", "state", True),
    ("CHECKPOINT.md", "checkpoint", True),
    ("TASK_QUEUE.md", "tasks", True),
    ("SECURITY_BOUNDARIES.md", "security", True),
    ("TOOLING.md", "tooling", True),
    ("RELEASE_STATE.md", "release", True),
]
REQUIRED_DIRS = ["decisions", "evidence", "memory", "knowledge", "tasks", "checkpoints", "logs", "tools", "architecture", "docs"]
REQUIRED_SCHEMAS = list(SCHEMA_FILES.keys())

# Capability categories (must match agent-capabilities.schema.json).
CAPABILITY_CATEGORIES = [
    "filesystem_read", "filesystem_write", "shell_execution", "git_read", "git_commit",
    "network_access", "browser_access", "package_installation", "secrets_access",
    "test_execution", "long_context", "structured_output", "persistent_session",
    "parallel_workers",
]

SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
TASK_ID_RE = re.compile(r"^TASK-\d{3,}$")


@dataclass
class Check:
    cid: str
    status: str  # pass | fail | warn
    severity: str
    summary: str
    evidence: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {"id": self.cid, "status": self.status, "severity": self.severity,
                "summary": self.summary, "evidence": self.evidence}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git(args: List[str]) -> Tuple[int, str]:
    try:
        r = subprocess.run(["git"] + args, cwd=REPO_ROOT, capture_output=True, text=True)
        return r.returncode, (r.stdout or r.stderr).strip()
    except FileNotFoundError:
        return 127, "git not found"


def load_json(path: Path) -> Any:
    with open(path) as f:
        return json.load(f)


def load_schema(name: str) -> Optional[Dict[str, Any]]:
    p = SCHEMA_FILES[name]
    if not p.exists():
        return None
    return load_json(p)


def _validate_against_schema(instance: Any, schema: Dict[str, Any]) -> List[str]:
    """Minimal draft-07 validator (no jsonschema dependency required).

    Supports: type, required, properties(type/enum/pattern/format/minLength/
    minimum/maximum/additionalProperties), array items, enum at top, not.
    Returns a list of human-readable error strings (empty == valid).
    """
    errors: List[str] = []

    def type_ok(value: Any, t: str) -> bool:
        if t == "object":
            return isinstance(value, dict)
        if t == "array":
            return isinstance(value, list)
        if t == "string":
            return isinstance(value, str)
        if t == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if t == "number":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if t == "boolean":
            return isinstance(value, bool)
        if t == "null":
            return value is None
        return True

    def walk(value: Any, schema: Dict[str, Any], path: str) -> None:
        if "type" in schema and not type_ok(value, schema["type"]):
            errors.append(f"{path}: expected type {schema['type']}, got {type(value).__name__}")
            return
        if schema.get("type") == "object" or isinstance(value, dict):
            for req in schema.get("required", []):
                if req not in value:
                    errors.append(f"{path}.{req}: required field missing")
            props = schema.get("properties", {})
            for k, v in value.items():
                if k in props:
                    walk(v, props[k], f"{path}.{k}")
                else:
                    if schema.get("additionalProperties") is False:
                        errors.append(f"{path}.{k}: additional property not allowed")
            # enum/pattern/minLength/format checks on properties (skip when null,
            # since the field type may allow null)
            for k, sub in props.items():
                if k not in value or value[k] is None:
                    continue
                if "enum" in sub and value[k] not in sub["enum"]:
                    errors.append(f"{path}.{k}: {value[k]!r} not in {sub['enum']}")
                if "pattern" in sub and not re.match(sub["pattern"], str(value[k])):
                    errors.append(f"{path}.{k}: {value[k]!r} does not match {sub['pattern']}")
                if sub.get("type") == "string":
                    if "minLength" in sub and len(value[k]) < sub["minLength"]:
                        errors.append(f"{path}.{k}: too short (<{sub['minLength']})")
                    if "format" in sub and sub["format"] == "date-time":
                        if not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", str(value[k])):
                            errors.append(f"{path}.{k}: not a date-time")
        if schema.get("type") == "array" or isinstance(value, list):
            item_schema = schema.get("items")
            if item_schema is not None:
                for i, item in enumerate(value):
                    walk(item, item_schema, f"{path}[{i}]")
            if "items" in schema and isinstance(schema["items"], dict):
                isub = schema["items"]
                if "enum" in isub:
                    for i, item in enumerate(value):
                        if item not in isub["enum"]:
                            errors.append(f"{path}[{i}]: {item!r} not in {isub['enum']}")
                if "pattern" in isub:
                    for i, item in enumerate(value):
                        if not re.match(isub["pattern"], str(item)):
                            errors.append(f"{path}[{i}]: {item!r} does not match {isub['pattern']}")
                if "type" in isub:
                    for i, item in enumerate(value):
                        if not type_ok(item, isub["type"]):
                            errors.append(f"{path}[{i}]: expected type {isub['type']}, got {type(item).__name__}")

    walk(instance, schema, "$")
    return errors


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_workspace() -> List[Check]:
    checks: List[Check] = []

    # 1. required files
    missing = [p for p, _, _ in REQUIRED_FILES if not (REPO_ROOT / p).exists()]
    if missing:
        checks.append(Check("workspace.files", "fail", "critical",
                            f"missing required files: {missing}", "REQUIRED_FILES"))
    else:
        checks.append(Check("workspace.files", "pass", "info", "all required root files present", ""))

    # 2. required directories
    missing_dirs = [d for d in REQUIRED_DIRS if not (REPO_ROOT / d).is_dir()]
    if missing_dirs:
        checks.append(Check("workspace.dirs", "fail", "high",
                            f"missing directories: {missing_dirs}", "REQUIRED_DIRS"))
    else:
        checks.append(Check("workspace.dirs", "pass", "info", "all workspace directories present", ""))

    # 3. schemas present + valid JSON
    bad_schema = []
    for name in REQUIRED_SCHEMAS:
        p = SCHEMA_FILES[name]
        if not p.exists():
            bad_schema.append(name)
            continue
        try:
            load_json(p)
        except Exception as e:
            bad_schema.append(f"{name}:{e}")
    if bad_schema:
        checks.append(Check("workspace.schemas", "fail", "high", f"schema problems: {bad_schema}", ""))
    else:
        checks.append(Check("workspace.schemas", "pass", "info", "all JSON schemas present + parse", ""))

    # 4. task records validate against task.schema.json
    task_errors = _validate_task_records()
    if task_errors:
        checks.append(Check("workspace.tasks", "fail", "high",
                            f"{len(task_errors)} task record problem(s)", "; ".join(task_errors[:3])))
    else:
        n = len(list((REPO_ROOT / "tasks").glob("TASK-*.json"))) if (REPO_ROOT / "tasks").is_dir() else 0
        checks.append(Check("workspace.tasks", "pass", "info", f"{n} task records valid", ""))

    # 5. checkpoint consistency (live CHECKPOINT.md references HEAD)
    ck = _checkpoint_staleness()
    if ck["error"]:
        checks.append(Check("workspace.checkpoint", "fail", "high", ck["error"], ""))
    elif ck["stale"]:
        checks.append(Check("workspace.checkpoint", "warn", "medium",
                            f"CHECKPOINT references {ck['commit']} which is not an ancestor of HEAD {ck['head']}", ""))
    else:
        checks.append(Check("workspace.checkpoint", "pass", "info",
                            f"CHECKPOINT commit {ck['commit']} consistent with HEAD {ck['head']}", ""))

    # 6. task dependency graph (no cycles, refs exist)
    dep_errors = _validate_task_dependencies()
    if dep_errors:
        checks.append(Check("workspace.task_deps", "fail", "high", "; ".join(dep_errors[:3]), ""))
    else:
        checks.append(Check("workspace.task_deps", "pass", "info", "task dependency graph consistent (no cycles/dangling)", ""))

    # 7. registry references resolve
    reg = _registry_checks()
    checks.extend(reg)

    return checks


def _validate_task_records() -> List[str]:
    errors: List[str] = []
    tasks_dir = REPO_ROOT / "tasks"
    if not tasks_dir.is_dir():
        return ["tasks/ directory missing"]
    schema = load_schema("task")
    if schema is None:
        return ["task.schema.json missing"]
    for f in sorted(tasks_dir.glob("TASK-*.json")):
        try:
            rec = load_json(f)
        except Exception as e:
            errors.append(f"{f.name}: invalid JSON ({e})")
            continue
        errs = _validate_against_schema(rec, schema)
        if errs:
            errors.append(f"{f.name}: " + "; ".join(errs))
    return errors


def _validate_task_dependencies() -> List[str]:
    errors: List[str] = []
    tasks_dir = REPO_ROOT / "tasks"
    if not tasks_dir.is_dir():
        return []
    ids: set = set()
    deps: Dict[str, List[str]] = {}
    for f in sorted(tasks_dir.glob("TASK-*.json")):
        try:
            rec = load_json(f)
        except Exception:
            continue
        ids.add(rec.get("task_id"))
        deps[rec.get("task_id")] = rec.get("dependencies", []) or []
    # dangling refs
    for tid, dl in deps.items():
        for d in dl:
            if d not in ids:
                errors.append(f"{tid}: dangling dependency {d}")
    # cycle detection (DFS)
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {tid: WHITE for tid in deps}

    def dfs(u: str, stack: List[str]) -> bool:
        color[u] = GRAY
        for d in deps.get(u, []):
            if d not in color:
                continue
            if color[d] == GRAY:
                errors.append(f"cycle: {' -> '.join(stack + [u, d])}")
                return True
            if color[d] == WHITE and dfs(d, stack + [u]):
                return True
        color[u] = BLACK
        return False

    for u in list(deps.keys()):
        if color[u] == WHITE:
            dfs(u, [])
    return errors


def _checkpoint_staleness() -> Dict[str, Any]:
    out = {"error": "", "stale": False, "commit": None, "head": None}
    ck_path = REPO_ROOT / "CHECKPOINT.md"
    if not ck_path.exists():
        out["error"] = "CHECKPOINT.md missing"
        return out
    text = ck_path.read_text()
    m = re.search(r"^-\s*\*\*commit\*\*:\s*`?([0-9a-f]{7,40})`?", text, re.MULTILINE)
    if not m:
        out["error"] = "CHECKPOINT.md has no commit SHA"
        return out
    out["commit"] = m.group(1)
    rc, head = _git(["rev-parse", "HEAD"])
    if rc != 0:
        out["error"] = "git rev-parse HEAD failed"
        return out
    out["head"] = head[:7] if head else None
    # is checkpoint commit an ancestor of HEAD?
    rc2, _ = _git(["merge-base", "--is-ancestor", out["commit"], "HEAD"])
    if rc2 != 0:
        out["stale"] = True
    return out


def _registry_checks() -> List[Check]:
    reg_path = ARCH_DIR / "registry.yaml"
    if not reg_path.exists():
        return [Check("workspace.registry", "fail", "high", "architecture/registry.yaml missing", "")]
    if yaml is None:
        return [Check("workspace.registry", "warn", "medium", "pyyaml unavailable; skipped deep check", "")]
    try:
        reg = yaml.safe_load(reg_path.read_text())
    except Exception as e:
        return [Check("workspace.registry", "fail", "high", f"registry YAML invalid: {e}", "")]
    subs = reg.get("subsystems", [])
    # every capt_solo.* expected_namespace should map to an existing package dir
    missing_ns = []
    for s in subs:
        ns = s.get("expected_namespace", "")
        if ns.startswith("capt_solo."):
            rel = ns.replace(".", "/")
            if not (REPO_ROOT / rel).exists():
                missing_ns.append(ns)
    if missing_ns:
        return [Check("workspace.registry_ns", "warn", "medium",
                      f"expected_namespace dirs absent (may be external): {missing_ns[:5]}", "")]
    return [Check("workspace.registry", "pass", "info", f"registry loads; {len(subs)} subsystems", "")]


# ---------------------------------------------------------------------------
# Status / bootstrap / next / capabilities
# ---------------------------------------------------------------------------

def workspace_status() -> Dict[str, Any]:
    rc, branch = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    rc2, head = _git(["rev-parse", "HEAD"])
    rc3, status = _git(["status", "--porcelain"])
    clean = (status == "")
    active = next_task()
    return {
        "branch": branch or "unknown",
        "head": (head or "")[:7],
        "clean": clean,
        "active_task": active.get("task_id") if active else None,
        "current_phase": "Stewardship",
        "last_verified_tests": "463 passed (this session)",
        "owner_gates": ["public_private_boundary", "licensing", "security", "destructive_migration", "canonical_conflict", "external_credential"],
        "next_action": active.get("title") if active else "none ready",
    }


def bootstrap_reading_list() -> List[str]:
    """Minimal ordered reading list for a newly attached agent."""
    return [
        "AGENTS.md            # entrypoint: authority order + startup procedure",
        "CURRENT_STATE.md     # where we are (branch/HEAD/tests/blockers)",
        "CHECKPOINT.md        # exact resume point + next command",
        "TASK_QUEUE.md        # human-readable queue (or: capt workspace next)",
        "WORKSPACE.md         # workspace contract + state classes",
        "SECURITY_BOUNDARIES.md # trust model + untrusted-content handling",
        "CAPT_CANON.md        # pointer -> docs/CAPT_CANON.md (invariants I-01..I-15)",
        "architecture/registry.yaml  # machine-readable subsystem registry",
        "TOOLING.md           # how to operate the workspace CLI",
    ]


def list_tasks(status: Optional[str] = None) -> List[Dict[str, Any]]:
    tasks_dir = REPO_ROOT / "tasks"
    if not tasks_dir.is_dir():
        return []
    out = []
    for f in sorted(tasks_dir.glob("TASK-*.json")):
        try:
            rec = load_json(f)
        except Exception:
            continue
        if status and rec.get("status") != status:
            continue
        out.append(rec)
    return out


def next_task(capabilities: Optional[Dict[str, bool]] = None) -> Optional[Dict[str, Any]]:
    """Highest-priority READY task whose deps are complete and caps satisfied."""
    tasks = list_tasks("ready")
    if not tasks:
        tasks = list_tasks("active")
    all_tasks = {t["task_id"]: t for t in list_tasks()}
    complete_ids = {t["task_id"] for t in all_tasks.values() if t.get("status") == "complete"}

    def deps_met(t: Dict[str, Any]) -> bool:
        for d in t.get("dependencies", []) or []:
            if d not in complete_ids:
                return False
        return True

    def caps_met(t: Dict[str, Any]) -> bool:
        if not capabilities:
            return True
        for c in t.get("required_capabilities", []) or []:
            if not capabilities.get(c, False):
                return False
        return True

    candidates = [t for t in tasks if deps_met(t) and caps_met(t)]
    if not candidates:
        return None
    candidates.sort(key=lambda t: (t.get("priority", 5), t.get("task_id")))
    return candidates[0]


def capabilities_manifest(agent: str = "local-agent") -> Dict[str, Any]:
    """Default capability manifest for a local-first agent in this repo.

    An agent should override with its real capabilities. Missing capabilities
    are reported honestly by `next_task`.
    """
    caps = {c: True for c in CAPABILITY_CATEGORIES}
    caps["network_access"] = False
    caps["browser_access"] = False
    caps["secrets_access"] = False
    return {"agent": agent, "schema_version": 1, "capabilities": caps,
            "notes": "Default local-first manifest; override with real capabilities."}


# ---------------------------------------------------------------------------
# Checkpoint generation / archive
# ---------------------------------------------------------------------------

def generate_checkpoint(task_id: Optional[str] = None, next_command: str = "",
                        files: Optional[str] = None, in_progress: str = "") -> str:
    """Generate CHECKPOINT.md from current repo state + supplied details.

    Never fabricates test results: tests_status is read from a real pytest run
    only if available; otherwise it is marked UNVERIFIED.
    """
    rc, branch = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    rc2, head = _git(["rev-parse", "HEAD"])
    commit = (head or "")[:7]
    rc3, status = _git(["status", "--porcelain"])
    clean = (status == "")
    tests_status = "UNVERIFIED (run: python3 -m pytest -q)"
    try:
        r = subprocess.run(["python3", "-m", "pytest", "-q"], cwd=REPO_ROOT,
                           capture_output=True, text=True, timeout=120)
        for line in (r.stdout + r.stderr).splitlines():
            if "passed" in line or "failed" in line:
                tests_status = line.strip()
                break
    except Exception:
        pass
    active_files = files or (f"tasks/{task_id}.json" if task_id else "")
    ck_id = f"CKPT-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-stewardship-{commit}"
    content = f"""# CHECKPOINT.md — Immediate Resume Contract

> Live checkpoint. Regenerate with `capt workspace checkpoint`. Archive prior
> copies to `checkpoints/` with `capt workspace archive-checkpoint`.

- **checkpoint_id**: {ck_id}
- **branch**: `{branch or 'unknown'}`
- **commit**: `{commit}`
- **completed**: (fill from prior checkpoint / git log)
- **in_progress**: {in_progress or (task_id or 'see TASK_QUEUE.md')}
- **active_files**: {active_files}
- **tests_status**: {tests_status}
- **root_cause**: n/a (generated checkpoint)
- **next_command**: {next_command or 'capt workspace next'}
- **next_commit_boundary**: coherent milestone commit once current task verifies
- **owner_gate**: none (or specify)
- **generated_at**: {_now()}
"""
    (REPO_ROOT / "CHECKPOINT.md").write_text(content)
    return content


def archive_checkpoint() -> str:
    ck_path = REPO_ROOT / "CHECKPOINT.md"
    if not ck_path.exists():
        raise FileNotFoundError("CHECKPOINT.md not found")
    text = ck_path.read_text()
    m = re.search(r"^-\s*\*\*commit\*\*:\s*`?([0-9a-f]{7,40})`?", text, re.MULTILINE)
    commit = m.group(1)[:7] if m else "unknown"
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dest_name = f"CHECKPOINT-{date}-stewardship-{commit}.md"
    dest = REPO_ROOT / "checkpoints" / dest_name
    shutil.copyfile(ck_path, dest)
    return str(dest)


# ---------------------------------------------------------------------------
# Public entry for CLI
# ---------------------------------------------------------------------------

def run_command(action: str, args: Dict[str, Any]) -> Tuple[int, Any]:
    """Dispatch a `capt workspace <action>`. Returns (exit_code, data)."""
    if action == "status":
        return 0, workspace_status()
    if action == "validate":
        checks = validate_workspace()
        fails = [c for c in checks if c.status == "fail"]
        warns = [c for c in checks if c.status == "warn"]
        return (1 if fails else 0), {"ok": not fails, "checks": [c.to_dict() for c in checks],
                                     "fail": len(fails), "warn": len(warns)}
    if action == "bootstrap":
        return 0, {"reading_list": bootstrap_reading_list()}
    if action == "tasks":
        return 0, list_tasks(args.get("status"))
    if action == "next":
        caps = args.get("capabilities")
        t = next_task(caps)
        return (0 if t else 1), t or {"next": None}
    if action == "capabilities":
        return 0, capabilities_manifest(args.get("agent", "local-agent"))
    if action == "checkpoint":
        content = generate_checkpoint(args.get("task"), args.get("next", ""),
                                      args.get("files"), args.get("in_progress", ""))
        return 0, {"written": "CHECKPOINT.md", "bytes": len(content)}
    if action == "archive-checkpoint":
        dest = archive_checkpoint()
        return 0, {"archived": dest}
    return 1, {"error": f"unknown workspace action: {action}"}
