#!/usr/bin/env python3
"""Manual CAPT-UPG-013 probe for component invalidation cost/behavior.

This does not benchmark provider prompt caching. It measures only local
ContextPack component-tree construction and change localization.
"""
from __future__ import annotations

import json
import sys
import time
from copy import deepcopy
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from capt_runtime.context_merkle import build_context_merkle, diff_context_merkle


def sample_pack():
    return {
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


def main():
    before_pack = sample_pack()
    after_pack = deepcopy(before_pack)
    after_pack["selectedRecords"][50]["digest"] = "sha256:" + "f" * 64
    iterations = 1000
    start = time.perf_counter()
    before = None
    for _ in range(iterations):
        before = build_context_merkle(before_pack)
    elapsed = time.perf_counter() - start
    after = build_context_merkle(after_pack)
    delta = diff_context_merkle(before, after)
    print(json.dumps({
        "iterations": iterations,
        "totalSeconds": elapsed,
        "meanMicroseconds": (elapsed / iterations) * 1_000_000.0,
        "changedComponents": delta["changedComponents"],
        "unchangedComponents": delta["unchangedComponents"],
        "providerCacheClaim": False,
    }, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
