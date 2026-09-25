#!/usr/bin/env python3
"""Exact-head empirical verification for CAPT upgrade probes.

This suite is intentionally separate from CAPT runtime dependencies. It turns
previous one-off/manual evidence obligations into deterministic CI evidence.
It does not promote experiments into authority or make provider-cache,
semantic-equivalence, context-sufficiency, or correctness claims.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

from capt_runtime.context_merkle import build_context_merkle, diff_context_merkle
from capt_runtime.discovery import ScanLimits, run_discovery
from capt_runtime.discovery.symbol_index import (
    build_symbol_index,
    select_symbols,
    sparse_selection_metrics,
)
from benchmarks.tree_sitter_hashing import hash_source_with_tree_sitter
from benchmarks.chunk_stability import (
    chunk_summary,
    compare_chunk_identity,
    fixed_size_chunks,
    optional_fastcdc_chunks,
)

ROOT = Path(__file__).resolve().parents[1]
RESULT_PATH = ROOT / "upgrade-probe-results.json"


def sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def git_sha() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def context_merkle_probe() -> Dict[str, Any]:
    # Same semantics as scripts/context_merkle_probe.py, but return structured
    # evidence to the aggregate CI artifact.
    before_pack = {
        "contextPackDigest": "sha256:" + "a" * 64,
        "policyVersion": 3,
        "triggerBoundary": 64000,
        "contextUsageBefore": 12000,
        "contextUsageAfter": 12000,
        "selectedRecords": [
            {
                "recordId": "mem-%d" % i,
                "digest": "sha256:" + ("%x" % (i % 16)) * 64,
                "retrievalScore": 0.5,
                "retrievalReason": "probe",
            }
            for i in range(100)
        ],
        "excludedRecords": [],
        "compressionActions": [],
        "summariesGenerated": [],
        "provenanceRetained": True,
        "unresolvedConflicts": [],
        "staleRecords": [],
        "redactions": [],
        "tokenBudget": 32000,
        "previousContextPackDigest": None,
        "missionId": "m-probe",
        "taskId": "t-probe",
        "driverRunId": "dr-probe",
    }
    after_pack = json.loads(json.dumps(before_pack))
    after_pack["selectedRecords"][50]["digest"] = "sha256:" + "f" * 64
    iterations = 1000
    started = time.perf_counter()
    before = None
    for _ in range(iterations):
        before = build_context_merkle(before_pack)
    elapsed = time.perf_counter() - started
    assert before is not None
    after = build_context_merkle(after_pack)
    delta = diff_context_merkle(before, after)
    assert delta["changedComponents"] == ["selection"]
    assert set(delta["unchangedComponents"]) == {
        "policy", "usage", "exclusions", "compression", "lineage"
    }
    assert before["semantics"]["providerCacheHitClaim"] is False
    return {
        "status": "probe_complete",
        "iterations": iterations,
        "totalSeconds": elapsed,
        "meanMicroseconds": (elapsed / iterations) * 1_000_000.0,
        "changedComponents": delta["changedComponents"],
        "unchangedComponents": delta["unchangedComponents"],
        "providerCacheClaim": False,
        "decision": "ACCEPT_COMPONENT_PROVENANCE_EXPERIMENT",
    }


def _seal_candidates_for_repo() -> Dict[str, Any]:
    limits = ScanLimits(
        max_depth=14,
        max_files=8000,
        max_directories=2500,
        max_bytes_per_file=8 * 1024 * 1024,
        max_total_bytes=256 * 1024 * 1024,
        max_candidates=8000,
        timeout_seconds=60.0,
    )
    candidates = []
    traces = []
    for rel in ("capt_runtime", "capt_ui/operator", "desktop"):
        target = ROOT / rel
        result = run_discovery(
            targets=[str(target)],
            allowed_roots=[str(ROOT)],
            limits=limits,
            guess_budget=1,
            requester="upgrade-probe-suite",
            request_id="probe-symbol-" + rel.replace("/", "-"),
        )
        assert result.termination == "source_present", (
            rel, result.termination, result.stop_reason
        )
        accepted = [dict(c) for c in result.candidates if c.get("accepted")]
        assert accepted, "SEAL admitted no candidates for %s" % rel
        candidates.extend(accepted)
        traces.append({
            "target": rel,
            "termination": result.termination,
            "acceptedCandidates": len(accepted),
            "confidence": result.source_location_confidence,
        })
    return {
        "root": str(ROOT),
        "classification": "source_present",
        "candidates": candidates,
        "sealRuns": traces,
    }


def _symbol_map(index: Mapping[str, Any]) -> Dict[tuple[str, str], Dict[str, Any]]:
    return {
        (str(item["path"]), str(item["qualname"])): dict(item)
        for item in index.get("symbols", []) or []
    }


def symbol_index_probe() -> Dict[str, Any]:
    discovery = _seal_candidates_for_repo()
    started = time.perf_counter()
    index = build_symbol_index(discovery)
    build_seconds = time.perf_counter() - started

    relevant_keys = {
        ("capt_ui/operator/runtime.py", "Operator.revoke_capability"),
        ("desktop/lease_command_service.py", "LeaseRuntimeCommandService.execute"),
        ("capt_runtime/services.py", "RuntimeService.revoke"),
        ("capt_runtime/services.py", "RuntimeService.check_lease"),
        ("capt_runtime/aggregates/capability.py", "CapabilityAggregate.revoke"),
        ("capt_runtime/aggregates/capability.py", "CapabilityAggregate.check_lease"),
    }
    by_key = _symbol_map(index)
    missing_labels = sorted(relevant_keys.difference(by_key))
    assert not missing_labels, "labeled real symbols missing from index: %r" % missing_labels
    relevant_ids = [by_key[key]["symbolId"] for key in sorted(relevant_keys)]

    selection_started = time.perf_counter()
    selection = select_symbols(
        index,
        ["revoke_capability", "check_lease", "revoke", "LeaseRuntimeCommandService"],
        max_symbols=12,
    )
    select_seconds = time.perf_counter() - selection_started
    metrics = sparse_selection_metrics(index, selection, relevant_ids)

    # A bounded automatic-selection recommendation requires high recall and
    # reasonable precision, but never implies context sufficiency.
    automatic_selection_eligible = (
        metrics["recall"] >= 0.80
        and metrics["precision"] >= 0.50
        and metrics["byteReductionRatio"] >= 0.50
    )

    # Edit-locality probe on the real RuntimeService.revoke symbol. Copy the
    # admitted source domains, make one same-line non-semantic byte edit, and
    # rebuild with the same accepted-candidate set rooted in the copy.
    with tempfile.TemporaryDirectory(prefix="capt-symbol-edit-") as td:
        copy_root = Path(td) / "repo"
        for rel in ("capt_runtime", "capt_ui", "desktop"):
            shutil.copytree(ROOT / rel, copy_root / rel)
        copied_candidates = []
        for candidate in discovery["candidates"]:
            path = Path(str(candidate.get("resolved_path") or candidate.get("path"))).expanduser()
            try:
                relative = path.resolve().relative_to(ROOT.resolve())
            except Exception:
                continue
            copied = copy_root / relative
            updated = dict(candidate)
            updated["path"] = str(copied)
            updated["resolved_path"] = str(copied.resolve())
            copied_candidates.append(updated)
        edited_discovery = {
            "root": str(copy_root),
            "classification": "source_present",
            "candidates": copied_candidates,
        }
        baseline = build_symbol_index(edited_discovery)
        baseline_map = _symbol_map(baseline)
        service_file = copy_root / "capt_runtime/services.py"
        lines = service_file.read_text(encoding="utf-8").splitlines(True)
        target_key = ("capt_runtime/services.py", "RuntimeService.revoke")
        target = baseline_map[target_key]
        line_index = int(target["lineStart"]) - 1
        original = lines[line_index]
        if original.endswith("\n"):
            lines[line_index] = original[:-1] + "  \n"
        else:
            lines[line_index] = original + "  "
        service_file.write_text("".join(lines), encoding="utf-8")
        edited = build_symbol_index(edited_discovery)
        edited_map = _symbol_map(edited)
        target_after = edited_map[target_key]
        neighbor_key = ("capt_runtime/services.py", "RuntimeService.check_lease")
        neighbor_before = baseline_map[neighbor_key]
        neighbor_after = edited_map[neighbor_key]
        assert target["symbolId"] == target_after["symbolId"]
        assert target["contentDigest"] != target_after["contentDigest"]
        assert neighbor_before["contentDigest"] == neighbor_after["contentDigest"]

    return {
        "status": "empirical_repository_probe_complete",
        "task": "trace capability revocation from operator control through runtime authority and subsequent lease rejection",
        "sealRuns": discovery["sealRuns"],
        "coverage": index["coverage"],
        "selected": [
            {"path": x["path"], "qualname": x["qualname"], "symbolId": x["symbolId"]}
            for x in selection["selected"]
        ],
        "labeledRelevantSymbols": [
            {"path": p, "qualname": q} for p, q in sorted(relevant_keys)
        ],
        "metrics": metrics,
        "indexBuildSeconds": build_seconds,
        "selectionSeconds": select_seconds,
        "editInvalidation": {
            "target": "capt_runtime/services.py:RuntimeService.revoke",
            "symbolIdentityStable": True,
            "targetContentDigestChanged": True,
            "neighborCheckLeaseDigestStable": True,
        },
        "automaticSparseSelectionEligibleForThisTask": automatic_selection_eligible,
        "contextSufficiencyProven": False,
        "decision": (
            "PROBE_COMPLETE_ACCEPT_LIMITED_AUTOMATIC_SELECTION"
            if automatic_selection_eligible
            else "PROBE_COMPLETE_REJECT_AUTOMATIC_SELECTION"
        ),
    }


def _ast_digest(source: bytes) -> str:
    tree = ast.parse(source.decode("utf-8"))
    return sha256(ast.dump(tree, include_attributes=False).encode("utf-8"))


def tree_sitter_probe() -> Dict[str, Any]:
    variants = {
        "base": b"def calculate(x):\n    return x + 1\n",
        "comment_whitespace": b"# note\ndef calculate( x ):\n    return x + 1  # trailing\n",
        "rename": b"def compute(x):\n    return x + 1\n",
        "literal": b"def calculate(x):\n    return x + 2\n",
        "refactor": b"def calculate(x):\n    y = x + 1\n    return y\n",
    }
    measured: Dict[str, Any] = {}
    for name, source in variants.items():
        started = time.perf_counter()
        result = hash_source_with_tree_sitter(source, "python")
        elapsed = time.perf_counter() - started
        assert result.get("status") == "ok", (name, result)
        assert result["semanticEquivalenceClaim"] is False
        assert result["behavioralEquivalenceClaim"] is False
        measured[name] = {
            "treeDigest": result["rootDigest"],
            "rawDigest": sha256(source),
            "astDigest": _ast_digest(source),
            "parseSeconds": elapsed,
        }

    base = measured["base"]
    expectations = {
        "comment_whitespace": False,
        "rename": True,
        "literal": True,
        "refactor": True,
    }
    false_stability = []
    false_invalidation = []
    comparisons = {}
    for name, expected_change in expectations.items():
        tree_changed = measured[name]["treeDigest"] != base["treeDigest"]
        raw_changed = measured[name]["rawDigest"] != base["rawDigest"]
        ast_changed = measured[name]["astDigest"] != base["astDigest"]
        comparisons[name] = {
            "expectedStructuralChange": expected_change,
            "treeChanged": tree_changed,
            "rawFileChanged": raw_changed,
            "pythonASTChanged": ast_changed,
        }
        if expected_change and not tree_changed:
            false_stability.append(name)
        if not expected_change and tree_changed:
            false_invalidation.append(name)

    # Real current-source grammar probes.
    actual = {}
    for language, path in (
        ("python", ROOT / "capt_runtime/services.py"),
        ("typescript", ROOT / "contracts/generated/typescript/src/types.ts"),
    ):
        source = path.read_bytes()
        started = time.perf_counter()
        result = hash_source_with_tree_sitter(source, language)
        elapsed = time.perf_counter() - started
        assert result.get("status") == "ok", (language, result)
        actual[language] = {
            "path": str(path.relative_to(ROOT)),
            "rootDigest": result["rootDigest"],
            "subtreeCount": len(result.get("subtrees") or []),
            "parseSeconds": elapsed,
        }

    assert not false_stability, false_stability
    assert not false_invalidation, false_invalidation
    return {
        "status": "tree_sitter_runtime_probe_complete",
        "comparisons": comparisons,
        "falseStabilityCases": false_stability,
        "falseInvalidationCases": false_invalidation,
        "actualSourceParses": actual,
        "semanticEquivalenceClaim": False,
        "behavioralEquivalenceClaim": False,
        "decision": "PROBE_COMPLETE_ACCEPT_STRUCTURAL_IDENTITY_ONLY",
    }


def _fastcdc(data: bytes) -> tuple[list[bytes], float]:
    started = time.perf_counter()
    result = optional_fastcdc_chunks(data, min_size=256, avg_size=512, max_size=1024)
    elapsed = time.perf_counter() - started
    assert result["status"] == "ok", result
    return list(result["chunks"]), elapsed


def fastcdc_probe() -> Dict[str, Any]:
    corpus = b"\n".join(
        (ROOT / rel).read_bytes()
        for rel in (
            "capt_runtime/services.py",
            "desktop/capt_runtime_service.py",
            "capt_runtime/store.py",
            "capt_ui/operator/runtime.py",
        )
    )
    mid = len(corpus) // 2
    edits = {
        "insert_beginning": b"CAPT_PROBE_INSERT\n" + corpus,
        "delete_middle": corpus[:mid] + corpus[mid + 256 :],
        "replace_middle": corpus[:mid] + (b"X" * min(256, len(corpus) - mid)) + corpus[mid + 256 :],
        "append": corpus + b"\nCAPT_PROBE_APPEND\n",
        "repetition": corpus + corpus[:4096] + corpus[:4096],
    }
    base_fixed = fixed_size_chunks(corpus, 512)
    base_fast, base_fast_seconds = _fastcdc(corpus)
    rows = []
    fixed_reuse = []
    fast_reuse = []
    fixed_churn = []
    fast_churn = []
    for name, edited in edits.items():
        started = time.perf_counter()
        fixed_after = fixed_size_chunks(edited, 512)
        fixed_seconds = time.perf_counter() - started
        fast_after, fast_seconds = _fastcdc(edited)
        fs = compare_chunk_identity(base_fixed, fixed_after)
        cs = compare_chunk_identity(base_fast, fast_after)
        fixed_reuse.append(fs["byteReuseRatio"])
        fast_reuse.append(cs["byteReuseRatio"])
        fixed_churn.append(fs["afterChunkChurnRatio"])
        fast_churn.append(cs["afterChunkChurnRatio"])
        rows.append({
            "edit": name,
            "fixed": {
                "summary": chunk_summary(fixed_after),
                "stability": fs,
                "runtimeSeconds": fixed_seconds,
            },
            "fastcdc": {
                "summary": chunk_summary(fast_after),
                "stability": cs,
                "runtimeSeconds": fast_seconds,
            },
        })
    avg_fixed_reuse = sum(fixed_reuse) / len(fixed_reuse)
    avg_fast_reuse = sum(fast_reuse) / len(fast_reuse)
    avg_fixed_churn = sum(fixed_churn) / len(fixed_churn)
    avg_fast_churn = sum(fast_churn) / len(fast_churn)
    local_advantage = (
        avg_fast_reuse >= avg_fixed_reuse
        and avg_fast_churn <= avg_fixed_churn
    )
    return {
        "status": "fastcdc_runtime_probe_complete",
        "corpusBytes": len(corpus),
        "base": {
            "fixed": chunk_summary(base_fixed),
            "fastcdc": chunk_summary(base_fast),
            "fastcdcRuntimeSeconds": base_fast_seconds,
        },
        "edits": rows,
        "aggregate": {
            "fixedMeanByteReuseRatio": avg_fixed_reuse,
            "fastcdcMeanByteReuseRatio": avg_fast_reuse,
            "fixedMeanChunkChurnRatio": avg_fixed_churn,
            "fastcdcMeanChunkChurnRatio": avg_fast_churn,
        },
        "llmPrefixCacheClaim": False,
        "providerCacheEvidence": None,
        "decision": (
            "PROBE_COMPLETE_ACCEPT_LOCAL_CHUNK_IDENTITY"
            if local_advantage
            else "PROBE_COMPLETE_REJECT_NO_CLEAR_LOCAL_ADVANTAGE"
        ),
    }


def cognitive_debt_live_probe() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="capt-debt-live-") as td:
        state = Path(td) / "state"
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        start = subprocess.run(
            ["capt", "start", "--state-dir", str(state), "--seed"],
            cwd=td,
            env=env,
            capture_output=True,
            text=True,
            timeout=45,
        )
        assert start.returncode == 0, {
            "stdout": start.stdout[-2000:],
            "stderr": start.stderr[-2000:],
        }
        sock = state / "runtime.sock"
        token = state / "runtime.token"
        try:
            for _ in range(100):
                if sock.exists() and token.exists():
                    break
                time.sleep(0.1)
            assert sock.exists() and token.exists(), "isolated runtime did not become ready"
            debt = subprocess.run(
                [
                    "capt-debt",
                    "--sock", str(sock),
                    "--token-file", str(token),
                    "--headless",
                ],
                cwd=td,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert debt.returncode == 0, {
                "stdout": debt.stdout[-2000:],
                "stderr": debt.stderr[-2000:],
            }
            payload = json.loads(debt.stdout)
            assert payload["opaqueScalarScore"] is None
            assert payload["automaticHalt"] is False
            assert payload["absenceOfDebtProvesCorrectness"] is False
            return {
                "status": "installed_live_headless_probe_complete",
                "itemCount": payload.get("itemCount"),
                "blockingItemCount": payload.get("blockingItemCount"),
                "categoryCounts": payload.get("categoryCounts"),
                "opaqueScalarScore": None,
                "automaticHalt": False,
                "absenceOfDebtProvesCorrectness": False,
                "decision": "IMPLEMENTED_EXACT_HEAD_LIVE_VERIFIED",
            }
        finally:
            subprocess.run(
                ["capt", "stop", "--state-dir", str(state)],
                cwd=td,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )


def main() -> int:
    result = {
        "schemaVersion": "1.0.0",
        "kind": "CAPTUpgradeProbeEvidence",
        "sourceSha": git_sha(),
        "claimBoundaries": {
            "providerPrefixCacheProven": False,
            "contextSufficiencyProven": False,
            "semanticEquivalenceProven": False,
            "behavioralEquivalenceProven": False,
            "absenceOfDebtProvesCorrectness": False,
        },
        "probes": {},
    }
    result["probes"]["upg013ContextMerkle"] = context_merkle_probe()
    result["probes"]["upg021SymbolIndex"] = symbol_index_probe()
    result["probes"]["upg022TreeSitter"] = tree_sitter_probe()
    result["probes"]["upg023FastCDC"] = fastcdc_probe()
    result["probes"]["upg024CognitiveDebt"] = cognitive_debt_live_probe()
    RESULT_PATH.write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
