#!/usr/bin/env python3
"""RRDS-1: full-tree census and falsifiable repository-review coverage receipts.

Read-only except explicit output JSON. No network; symlinks are not followed.
Passing proves path/digest accounting, NOT that review conclusions are correct.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SOURCE = frozenset((".py", ".swift", ".sh", ".zsh", ".go", ".rs", ".c", ".h",
                    ".m", ".mm", ".cc", ".cpp", ".hpp", ".java", ".kt", ".js",
                    ".ts", ".jsx", ".tsx", ".lua", ".sql", ".proto", ".rb"))
RISK = re.compile("auth|approval|capabilit|credential|crypto|encrypt|exec|"
                  "keychain|permission|process|runtime|sandbox|secret|socket|token",
                  re.I)
RECEIPT_LINE = re.compile(r"\bL\d+(?:-L?\d+)?\b")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def head(root: Path) -> str | None:
    p = subprocess.run(("git", "-C", str(root), "rev-parse", "--verify", "HEAD"),
                       capture_output=True, text=True, check=False, timeout=15)
    return p.stdout.strip() if p.returncode == 0 else None


def census(root: Path, excluded: set[str] | None = None) -> dict:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"not a directory: {root}")
    excluded = excluded or set()
    if any(not x or "/" in x or x in {".", "..", ".git"} for x in excluded):
        raise ValueError("unsafe exclusion")
    records, directories, missing, skipped, links = [], [], [], [], []
    def fail(exc: OSError) -> None:
        missing.append(f"{exc.filename}: {exc.strerror}")
    for parent, dirs, files in os.walk(root, followlinks=False, onerror=fail):
        base = Path(parent)
        directories.append(base.relative_to(root).as_posix())
        keep = []
        for name in sorted(dirs):
            p = base / name
            rel = p.relative_to(root).as_posix()
            if p.is_symlink():
                links.append(rel)
            elif name == ".git":
                continue
            elif name in excluded:
                skipped.append(rel)
            else:
                keep.append(name)
        dirs[:] = keep
        for name in sorted(files):
            p = base / name
            rel = p.relative_to(root).as_posix()
            try:
                # Linked Git worktrees store repository-control metadata in a
                # regular root-level .git pointer file (rather than a .git
                # directory). Do not hash that checkout-specific pointer as
                # project content; preserve detection of unresolved symlinks.
                if base == root and name == ".git" and p.is_file() and not p.is_symlink():
                    continue
                if p.is_symlink():
                    links.append(rel)
                elif p.is_file():
                    suffix = p.suffix.lower()
                    records.append(dict(path=rel, bytes=p.stat().st_size, sha256=digest(p),
                                        source=suffix in SOURCE,
                                        risk=bool(suffix in SOURCE and RISK.search(rel))))
                else:
                    missing.append(f"{rel}: not regular file")
            except OSError as exc:
                missing.append(f"{rel}: {type(exc).__name__}")
    records.sort(key=lambda x: x["path"])
    source_dirs = sorted({str(Path(x["path"]).parent) for x in records if x["source"]})
    return dict(schema="capt.rrds.census.v1", root=str(root), head=head(root),
                files=records, directories=sorted(directories),
                source_directories=source_dirs, exclusions=sorted(skipped),
                symlinks=sorted(links), errors=sorted(missing))


def verify(c: dict, inspection: dict, minimum: float = 0.70) -> dict:
    if c.get("schema") != "capt.rrds.census.v1":
        raise ValueError("invalid census schema")
    if inspection.get("schema") != "capt.rrds.inspection.v1":
        raise ValueError("invalid inspection schema")
    if not (0 <= minimum <= 1):
        raise ValueError("invalid threshold")
    problems = []
    root = Path(c["root"])
    expected = {x["path"]: x for x in c["files"]}
    current = census(root)
    actual = {x["path"]: x for x in current["files"]}
    if not c.get("head") or c["head"] != current["head"]:
        problems.append("unpinned or changed Git HEAD")
    if len(expected) != len(c["files"]):
        problems.append("duplicate census paths")
    if set(expected) != set(actual):
        problems.append("tree membership drift")
    if c.get("root") != current["root"]:
        problems.append("census root drift")
    if sorted(c.get("source_directories", [])) != current["source_directories"]:
        problems.append("source directory classification drift")
    if c.get("directories") != current["directories"]:
        problems.append("directory census drift")
    for path in sorted(set(expected) & set(actual)):
        if expected[path].get("sha256") != actual[path]["sha256"]:
            problems.append(f"changed bytes: {path}")
        for field in ("bytes", "source", "risk"):
            if expected[path].get(field) != actual[path][field]:
                problems.append(f"census {field} classification drift: {path}")
    if current["errors"] or c.get("errors"):
        problems.append("inaccessible or unreadable files")
    if current["symlinks"] != c.get("symlinks") or current["symlinks"]:
        problems.append("unresolved symlinks")
    if c.get("exclusions"):
        problems.append("explicit exclusions remain outside reviewed scope")
    inspections = inspection.get("inspected")
    critical = inspection.get("critical_paths")
    if not isinstance(inspections, list) or not isinstance(critical, list):
        raise ValueError("inspected and critical_paths must be arrays")
    observed = set()
    structurally_verified = set()
    for row in inspections:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            problems.append("invalid file receipt")
            continue
        path = row["path"]
        if path in observed:
            problems.append(f"duplicate file receipt: {path}")
        observed.add(path)
        if path not in expected:
            problems.append(f"unknown inspected file: {path}")
        elif row.get("sha256") != expected[path]["sha256"]:
            problems.append(f"receipt hash mismatch: {path}")
        elif not RECEIPT_LINE.search(str(row.get("line_evidence", ""))):
            problems.append(f"line evidence absent: {path}")
        elif not row.get("node_evidence_ref"):
            problems.append(f"journaled read receipt absent: {path}")
        else:
            line_ref = str(row.get("line_evidence", ""))
            references = RECEIPT_LINE.findall(line_ref)
            if len(references) != 1:
                problems.append(f"ambiguous source-line span: {path}")
                continue
            checksum = row.get("line_sha256")
            if not isinstance(checksum, str) or not re.fullmatch(r"[0-9a-f]{64}", checksum):
                problems.append(f"source-line checksum absent or malformed: {path}")
                continue
            token = references[0][1:]
            ends = token.split("-", 1)
            first = int(ends[0])
            last = int(ends[1].removeprefix("L")) if len(ends) == 2 else first
            lines = (root / path).read_bytes().splitlines(keepends=True)
            # L0 is the only valid reference for an empty source file.
            if not ((first == last == 0 and not lines) or
                    (1 <= first <= last <= len(lines))):
                problems.append(f"source-line span outside file: {path}")
                continue
            excerpt = b"" if first == 0 else b"".join(lines[first - 1:last])
            if hashlib.sha256(excerpt).hexdigest() != checksum:
                problems.append(f"source-line checksum mismatch: {path}")
            else:
                structurally_verified.add(path)
    # Coverage must be computed from a freshly generated local census,
    # not from the adversarial/submitted source/risk classification.
    source = {x["path"] for x in current["files"] if x["source"]}
    reviewed = structurally_verified & source
    present_dirs = {str(Path(path).parent) for path in reviewed}
    absent_dirs = sorted(set(current["source_directories"]) - present_dirs)
    if absent_dirs:
        problems.append(f"{len(absent_dirs)} uninspected source directories")
    risk = {x["path"] for x in current["files"] if x["risk"]}
    undeclared = sorted(risk - set(critical))
    missing_critical = sorted(set(critical) - structurally_verified)
    if undeclared:
        problems.append(f"{len(undeclared)} undeclared risk candidates")
    if missing_critical:
        problems.append(f"{len(missing_critical)} uninspected critical paths")
    if not critical and source:
        problems.append("critical path declaration missing")
    if not source:
        problems.append("no source files found; cannot certify deep review")
    fraction = len(reviewed) / len(source) if source else 0.0
    if fraction < minimum:
        problems.append(f"source-file breadth {fraction:.1%} < diagnostic floor {minimum:.1%}")
    if fraction < 1.0:
        problems.append("incomplete first-party source-file receipts; deep review requires 100%")
    structural_status = "PASS" if not problems else "FAIL"
    # The inspection document is claimant-controlled. A nonempty Node reference
    # does not establish that CAPT Node returned the claimed file bytes.
    # Fail closed until a trusted live Node journal/evidence verifier is integrated.
    if structural_status == "PASS":
        problems.append("authenticated CAPT Node read verification unavailable; claimant-supplied node_evidence_ref is not proof")
    return dict(status="PARTIAL_OR_UNVERIFIED", structural_status=structural_status,
                git_head=c.get("head"), source_files=len(source),
                inspected_source_files=len(reviewed), source_directories=len(current["source_directories"]),
                inspected_source_directories=len(present_dirs & set(current["source_directories"])),
                uninspected_directories=absent_dirs, uninspected_critical=missing_critical,
                undeclared_risk=undeclared, problems=problems,
                caveat="Structural source-byte coverage is not authenticated CAPT Node provenance or semantic review.")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="action", required=True)
    a = sub.add_parser("inventory")
    a.add_argument("--repo", required=True, type=Path)
    a.add_argument("--output", required=True, type=Path)
    a.add_argument("--exclude-dir", action="append", default=[])
    b = sub.add_parser("verify")
    b.add_argument("--census", required=True, type=Path)
    b.add_argument("--inspection", required=True, type=Path)
    b.add_argument("--min-source-fraction", type=float, default=0.70)
    b.add_argument("--output", type=Path)
    c = sub.add_parser("ci")
    c.add_argument("--index", required=True, type=Path)
    args = p.parse_args()
    try:
        if args.action == "inventory":
            result = census(args.repo, set(args.exclude_dir))
            args.output.write_text(json.dumps(result, indent=2) + "\n")
            print(f"CENSUS {result['root']} {len(result['files'])} files")
            return 0 if not result["errors"] else 1
        if args.action == "verify":
            result = verify(json.loads(args.census.read_text()),
                            json.loads(args.inspection.read_text()), args.min_source_fraction)
            output = json.dumps(result, indent=2) + "\n"
            if args.output:
                args.output.write_text(output)
            print(output)
            return 0 if result["status"] == "DEEP_COVERAGE_GATE_PASS" else 1
        index = json.loads(args.index.read_text())
        if index.get("schema") != "capt.rrds.index.v1" or not isinstance(index.get("reviews"), list):
            raise ValueError("invalid review evidence index")
        workspace = args.index.resolve().parent.parent
        failed = False
        for item in index["reviews"]:
            if not isinstance(item, dict) or set(item) != {"census", "inspection"}:
                raise ValueError("review index item requires census and inspection paths")
            paths = []
            for key in ("census", "inspection"):
                rel = Path(item[key])
                candidate = (workspace / rel).resolve()
                if candidate != workspace and workspace not in candidate.parents:
                    raise ValueError("evidence index points outside CI workspace")
                paths.append(candidate)
            outcome = verify(json.loads(paths[0].read_text()), json.loads(paths[1].read_text()))
            print(outcome["status"], outcome["git_head"], outcome["problems"])
            failed |= outcome["status"] != "DEEP_COVERAGE_GATE_PASS"
        event_file = os.environ.get("GITHUB_EVENT_PATH")
        if event_file and Path(event_file).is_file():
            evt = json.loads(Path(event_file).read_text())
            body = str((evt.get("pull_request") or {}).get("body") or "")
            if "RRDS-1: PASS" in body and not index["reviews"]:
                print("RRDS-1: explicit PASS claimed without indexed receipts", file=sys.stderr)
                failed = True
        # A zero-row index means no *deep review* is being certified, not a reviewed repo.
        print("RRDS-1 evidence records checked:", len(index["reviews"]))
        return 1 if failed else 0
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print(f"RRDS-1 ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
