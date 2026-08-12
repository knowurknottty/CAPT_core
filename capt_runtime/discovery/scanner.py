"""Bounded SEAL local scanner (v0.7).

Read-only, allow-listed, symlink-escape-safe discovery of local files/dirs.

Guarantees:
  * never mutates the environment (write/rename/unlink/chmod/execute/upload are
    absent from the API by construction);
  * every tokenized path is realpath-resolved and must resolve beneath an
    allowed root, else it is rejected (outside_allowed_root / symlink_escape);
  * bounded by configurable ScanLimits; no unbounded recursion;
  * output is deterministic, redacted, and split into candidate + rejection
    ledgers.

The scanner classifies observations; it never draws target-repository
conclusions and never grants or enlarges any capability.
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .models import (
    AMBIGUOUS,
    COMPILED_ARTIFACT_ONLY,
    NOT_FOUND,
    PERMISSION_DENIED,
    PROJECT_MARKER_PRESENT,
    REJECTED,
    SOURCE_FILE_PRESENT,
    SOURCE_PRESENT,
    ScanLimits,
)
from .policy import DEFAULT_POLICY, ClassificationPolicy
from .provenance import observation_provenance
from .redaction import normalize_path, redact_text


class PathSafetyError(Exception):
    """A path could not be safely authorized (escape / non-resolvable)."""


def _resolve_under_root(candidate_path: str,
                        allowed_roots: Sequence[str]) -> Tuple[Optional[str], Optional[str]]:
    """Return (resolved_realpath, None) if candidate resolves under an allowed
    root; else (None, reason). Handles symlinks/../aliases via realpath."""
    try:
        resolved = str(Path(candidate_path).resolve(strict=False))
    except (OSError, RuntimeError):
        return None, "unresolvable_path"
    for ar in allowed_roots:
        ar_real = str(Path(ar).expanduser().resolve(strict=False))
        if resolved == ar_real or resolved.startswith(ar_real + os.sep):
            return resolved, None
    return None, "outside_allowed_root"


class BoundedLocalScanner:
    """Read-only, allow-listed, bounded local discovery scanner (SEAL)."""

    def __init__(self, policy: Optional[ClassificationPolicy] = None,
                 limits: Optional[ScanLimits] = None,
                 allowed_roots: Optional[Sequence[str]] = None,
                 expected_markers: Optional[Sequence[str]] = None) -> None:
        self._policy = policy or DEFAULT_POLICY
        self._limits = limits or ScanLimits()
        self._allowed_roots = tuple(str(Path(r).expanduser())
                                    for r in (allowed_roots or []))
        # Target-criteria gate: if set, terminal SOURCE_PRESENT requires at
        # least one of these markers actually present (Case-D wrong-repo guard).
        self._expected_markers = tuple(expected_markers or ())

    # ---- public API -------------------------------------------------------
    def with_roots(self, allowed_roots: Sequence[str]) -> "BoundedLocalScanner":
        return BoundedLocalScanner(self._policy, self._limits, allowed_roots,
                                   self._expected_markers)

    def scan(self, root: str, *, strategy: str = "KNOWN_PATH",
             boundaries: Optional[Dict[str, Any]] = None,
             run_id: str = "", request_id: str = "") -> Dict[str, Any]:
        """Scan a root within allowlisted roots (or, if none configured, the
        single explicit root only). Returns a deterministic bounded result.

        ``run_id``/``request_id`` (optional) are threaded into per-candidate
        provenance so each observation is traceable to its parent run.
        """
        started = time.monotonic()
        bounds = dict(boundaries or {})
        limits = self._limits if "limits" not in bounds else bounds["limits"]
        allowed = self._allowed_roots or (boundaries or {}).get("allowed_roots", [])

        root_p = str(Path(root).expanduser())
        # Root allowlist: if roots are declared, the scan root must be within one.
        if allowed:
            resolved_root, err = _resolve_under_root(root_p, allowed)
            if err:
                return self._base_result(
                    REJECTED, "outside_allowed_root", root_p, started,
                    rejections=[(root_p, "outside_allowed_root")], run_id=run_id,
                    request_id=request_id)
        else:
            # Explicit single root acts as its own allowlist; still resolve it.
            resolved_root = str(Path(root_p).resolve(strict=False))

        # existence / readability
        if not Path(root_p).exists():
            return self._base_result(NOT_FOUND, "path does not exist", root_p,
                                     started, run_id=run_id, request_id=request_id)
        if not os.access(root_p, os.R_OK):
            return self._base_result(PERMISSION_DENIED, "path not readable",
                                     root_p, started, run_id=run_id,
                                     request_id=request_id)
        # symlink-escape: resolved root must remain within allowlist
        if allowed:
            rr, err = _resolve_under_root(root_p, allowed)
            if err:
                return self._base_result(REJECTED, "symlink_escape", root_p,
                                         started,
                                         rejections=[(root_p, err)],
                                         run_id=run_id, request_id=request_id)

        return self._walk(root_p, allowed, limits, std_strategy=strategy,
                          started=started, run_id=run_id, request_id=request_id)

    # ---- internals --------------------------------------------------------
    def _walk(self, root, allowed, limits, *, std_strategy, started, run_id="",
              request_id=""):
        candidates: List[Dict[str, Any]] = []
        rejections: List[Tuple[str, str]] = []
        n_source = n_bundle = n_git = n_marker = 0
        n_expected = 0
        n_dirs = n_files = n_bytes = n_pruned_dirs = 0

        def check_budget():
            if time.monotonic() - started > limits.timeout_seconds:
                return "timeout"
            # Independent hard count guards: max_files means FILES, max_directories
            # means DIRECTORIES (each enforced on its own metric).
            if n_files >= limits.max_files:
                return "file_count"
            if n_dirs >= limits.max_directories:
                return "dir_count"
            # Separate combined node-count guard (an additional total bound) that
            # includes files + descended dirs + pruned (skipped) dirs, so a huge
            # heavy-dir tree still cannot be walked unboundedly.
            if n_files + n_dirs + n_pruned_dirs >= limits.max_files + limits.max_directories:
                return "node_count"
            if n_bytes >= limits.max_total_bytes:
                return "total_bytes"
            if len(candidates) >= limits.max_candidates:
                return "candidate_count"
            return None

        for dirpath, dirnames, filenames in os.walk(root, topdown=True):
            budget = check_budget()
            if budget:
                rejections.append((dirpath, budget))
                break
            # depth bound
            depth = dirpath[len(root):].count(os.sep)
            if depth > limits.max_depth:
                dirnames[:] = []
                continue
            # prune heavy dirs; count directories
            pruned = []
            for d in dirnames:
                full = os.path.join(dirpath, d)
                if self._policy.is_bundle_dir(d):
                    n_bundle += 1
                    candidates.append(self._candidate(
                        full, strategy=std_strategy,
                        classification=COMPILED_ARTIFACT_ONLY, kind="dir",
                        confidence="low", allowed=allowed, root=root,
                        run_id=run_id, request_id=request_id))
                    continue
                if d in (".git",):
                    n_git += 1
                    pruned.append(d)  # don't descend into .git internals
                    continue
                if d in (".venv", "venv", "__pycache__", "node_modules",
                         "target", "dist", "build"):
                    # Too heavy to recurse: count under a SEPARATE pruned-dir
                    # budget (n_pruned_dirs), never charged to max_files.
                    # max_files counts FILES only; these are directories.
                    n_pruned_dirs += 1
                    continue
                pruned.append(d)
                n_dirs += 1
                # Independent dir-count cap: stop descending once max_directories
                # directories have been admitted, so a single wide level cannot
                # exceed the directory bound.
                if n_dirs >= limits.max_directories:
                    break
            dirnames[:] = pruned
            for fn in filenames:
                budget = check_budget()
                if budget:
                    rejections.append((os.path.join(dirpath, fn), budget))
                    break
                if n_files >= limits.max_files:
                    rejections.append((os.path.join(dirpath, fn), "file_count"))
                    break
                fp = os.path.join(dirpath, fn)
                # symlink-escape per file
                if allowed:
                    rr, err = _resolve_under_root(fp, allowed)
                    if rr is None:
                        rejections.append((fp, "symlink_escape"))
                        continue
                else:
                    rr = str(Path(fp).resolve(strict=False))
                # size bounds
                try:
                    sz = os.path.getsize(fp)
                except OSError:
                    rejections.append((fp, "permission_denied"))
                    continue
                if sz > limits.max_bytes_per_file:
                    rejections.append((fp, "size_limit"))
                    continue
                n_bytes += sz
                n_files += 1
                if self._policy.is_source_file(fn):
                    n_source += 1
                    is_marker = fn in ("pyproject.toml", "setup.py", "setup.cfg",
                                       "package.json", "go.mod", "Cargo.toml",
                                       "Makefile", "AGENTS.md", "README.md")
                    if is_marker:
                        n_marker += 1
                    if self._expected_markers and fn in self._expected_markers:
                        n_expected += 1
                    # Candidate-level observation vocabulary: a source FILE or a
                    # project MARKER is present (WHAT was observed). Target-match
                    # is a SEPARATE aggregate-level conclusion (SOURCE_PRESENT)
                    # gated by expected_markers, so a candidate never overstates
                    # target identity on its own.
                    cand_class = (PROJECT_MARKER_PRESENT if is_marker
                                  else SOURCE_FILE_PRESENT)
                    candidates.append(self._candidate(
                        fp, strategy=std_strategy, classification=cand_class,
                        kind="file", confidence="high", allowed=allowed,
                        root=root, run_id=run_id, request_id=request_id,
                        evidence=["%s present" % fn]))
                elif self._policy.is_bundle_file(fn):
                    n_bundle += 1
                    candidates.append(self._candidate(
                        fp, strategy=std_strategy,
                        classification=COMPILED_ARTIFACT_ONLY, kind="bundle",
                        confidence="low", allowed=allowed, root=root,
                        run_id=run_id, request_id=request_id))
                else:
                    rejections.append((fp, "not_source_tree"))

        classification = self._policy.classify_tree(
            n_source_files=n_source, n_bundle_artifacts=n_bundle,
            has_git=(n_git > 0), has_project_marker=(n_marker > 0),
            has_only_bundle=(n_bundle > 0 and n_source == 0))

        # Target-criteria gate (Case D): if expected markers were requested and
        # none matched, do NOT emit a terminal SOURCE_PRESENT conclusion.
        if self._expected_markers and classification == SOURCE_PRESENT:
            if n_expected == 0:
                classification = "possible_repository"
                confidence = "low"
            else:
                confidence = "high"
        else:
            confidence = self._confidence(classification)

        return {
            "root": normalize_path(root),
            "strategy": std_strategy,
            "classification": classification,
            "confidence": confidence,
            "n_source_files": n_source,
            "n_bundle_artifacts": n_bundle,
            "candidates": candidates,
            "rejections": rejections,
            "termination": "source_present" if classification == SOURCE_PRESENT
            else ("compiled_artifact_only" if n_bundle > 0 and n_source == 0
                  else ("possible_repository" if classification == "possible_repository"
                        else "not_found")),
            "stop_reason": None,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "limits": {k: getattr(limits, k) for k in
                       ("max_depth", "max_files", "max_directories",
                        "max_bytes_per_file", "max_total_bytes",
                        "max_candidates", "timeout_seconds")},
        }

    def _candidate(self, fp, *, strategy, classification, kind, confidence,
                   allowed, root, run_id, request_id, evidence=None) -> Dict[str, Any]:
        resolved = str(Path(fp).resolve(strict=False))
        prov = observation_provenance(
            run_id=run_id or "(standalone)",
            strategy=strategy, root=normalize_path(root),
            classification=classification, confidence=confidence,
            redactions=[], accepted=True)
        return {
            "candidate_id": "cand-" + uuid.uuid4().hex[:12],
            "path": normalize_path(fp),
            "resolved_path": normalize_path(resolved),
            "kind": kind,
            "strategy": strategy,
            "classification": classification,
            "confidence": confidence,
            "evidence": [redact_text(e) for e in (evidence or [])],
            "redactions": [],
            "provenance": prov,
            "accepted": True,
        }

    def _base_result(self, classification, stop_reason, root, started,
                     rejections=None, run_id="", request_id="") -> Dict[str, Any]:
        if run_id:
            prov = observation_provenance(
                run_id=run_id, strategy="KNOWN_PATH", root=normalize_path(root),
                classification=classification, confidence=self._confidence(classification),
                redactions=[], accepted=False)
        else:
            prov = {}
        return {
            "root": normalize_path(root),
            "strategy": "KNOWN_PATH",
            "classification": classification,
            "confidence": self._confidence(classification),
            "n_source_files": 0,
            "n_bundle_artifacts": 0,
            "candidates": [],
            "rejections": list(rejections or []),
            "termination": ("rejected" if classification == REJECTED
                            else classification),
            "stop_reason": stop_reason,
            "run_provenance": prov if run_id else None,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "limits": {k: getattr(self._limits, k) for k in
                       ("max_depth", "max_files", "max_directories",
                        "max_bytes_per_file", "max_total_bytes",
                        "max_candidates", "timeout_seconds")},
        }

    @staticmethod
    def _confidence(classification: str) -> str:
        return {"source_present": "high",
                "possible_repository": "medium",
                "compiled_artifact_only": "low"}.get(classification, "low")
