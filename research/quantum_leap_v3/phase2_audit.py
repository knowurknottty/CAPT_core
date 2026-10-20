"""Quantum Leap v3 — immutable Git-object predicate audit, no provider calls.
Consumes the maintainer-supplied 52-claim fixture and the experimental compiler.
Does not modify CAPT RuntimeService, authorize actions or promote claims.
"""
from __future__ import annotations
import collections
import copy
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import importlib.util
_SPEC = importlib.util.spec_from_file_location("ql_phase2_beliefprobe", Path(__file__).with_name("beliefprobe.py"))
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError("local predicate verifier not found")
bp = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bp)

PINS = ("c5b6f6a", "3f11800", "e28b665")
ALLOWED = {bp.WITHIN, bp.EXCEEDS, bp.UNSUPPORTED, bp.INCONCLUSIVE}

def call(repo, *args):
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=30)
    if p.returncode:
        raise RuntimeError("git failed: " + p.stderr[:180])
    return p.stdout.strip()

def mutate(original):
    if not original.get("kind"):
        return None
    cl = copy.deepcopy(original)
    a, k = cl["args"], cl["kind"]
    if k == "symbol_at_line":
        a["line"] = int(a["line"]) + 7
    elif k == "symbol_defined":
        a["name"] += "_intentionally_absent_ql"
    elif k == "path_exists":
        a["path"] += ".intentionally_absent_ql"
    elif k in ("pattern_count", "collection_size", "file_count", "line_total"):
        n, op = int(a["n"]), a["op"]
        if op == "==":
            a["n"] = n + 1
        elif op in (">=", ">"):
            a["op"], a["n"] = "<", n
        elif op in ("<=", "<"):
            a["op"], a["n"] = ">", n
    elif k == "schema_property_absent":
        a["regex"] = "."
    else:
        return None
    return cl

def examine(repo, claims, pin):
    tree = bp.Tree(str(repo), pin)
    rows = []
    for cl in claims:
        result = bp.evaluate(tree, cl)
        if result["predicate_status"] not in ALLOWED:
            raise AssertionError("invalid predicate status")
        assert result["promotion_eligible"] is False
        assert result["semantic_entailment"] == "NOT_ASSESSED"
        rows.append({"id": cl["id"], "source": cl["source"], "fidelity": cl["fidelity"],
                     **result})
    return tree.commit, rows

def summary(rows):
    counts = collections.Counter(r["predicate_status"] for r in rows)
    n = len(rows)
    full_within = sum(r["fidelity"] == "full" and r["predicate_status"] == bp.WITHIN for r in rows)
    return {
        "total": n, "compiled": n-counts[bp.UNSUPPORTED],
        "status_counts": {status:counts[status] for status in (bp.WITHIN,bp.EXCEEDS,bp.UNSUPPORTED,bp.INCONCLUSIVE)},
        "full_fidelity_within": full_within, "D_proxy": n-full_within,
        "unconfirmed_claim_ids": [r["id"] for r in rows if r["fidelity"] != "full" or r["predicate_status"] != bp.WITHIN],
        "exceptions": [{"id":r["id"],"fidelity":r["fidelity"],"status":r["predicate_status"],"detail":r["detail"]}
                       for r in rows if r["predicate_status"] != bp.WITHIN]
    }

def run(repo: Path, claims_path: Path, history: bool):
    raw = claims_path.read_bytes()
    claims = json.loads(raw)
    if len(claims)!=52 or len({c["id"] for c in claims})!=52:
        raise AssertionError("v3 original corpus must have exactly 52 unique claims")
    result = {
        "verification_scope": "predicates only; no independent claim-to-probe semantic entailment",
        "promotion_eligible": False,
        "author_supplied_fidelity": True,
        "D_proxy_definition": "52 - count(full-fidelity claims with WITHIN predicate verdict)",
        "D_proxy_is_not_semantic_certainty_debt": True,
        "source_corpus_sha256": hashlib.sha256(raw).hexdigest(),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "pins": {}
    }
    for p in PINS:
        sha, rows = examine(repo, claims, p)
        result["pins"][p] = {"sha":sha, "summary":summary(rows), "claims":rows}
    latest = bp.Tree(str(repo), PINS[-1])
    mutation = []
    for cl in claims:
        baseline = bp.evaluate(latest, cl)
        altered = mutate(cl)
        if baseline["predicate_status"] == bp.WITHIN and altered:
            outcome = bp.evaluate(latest, altered)
            mutation.append({"id":cl["id"],"mutant_status":outcome["predicate_status"],
                             "killed":outcome["predicate_status"] == bp.EXCEEDS})
    result["mutation_at_head"] = {
        "scope": "predicate perturbation only, NOT tree mutation or proof of semantic entailment",
        "eligible":len(mutation),"killed":sum(x["killed"] for x in mutation),
        "survivors":[m for m in mutation if not m["killed"]],
        "per_claim":mutation
    }
    if history:
        since="2026-10-08T00:00:00+00:00"
        commits=list(reversed(call(repo,"rev-list","--first-parent",f"--since={since}",PINS[-1]).splitlines()))
        transitions={x["id"]:[] for x in claims}
        previous={}
        for sha in commits:
            tree=bp.Tree(str(repo),sha)
            for c in claims:
                current=bp.evaluate(tree,c)["predicate_status"]
                last=previous.get(c["id"])
                if last is not None and last!=current:
                    transitions[c["id"]].append({"commit":sha[:12],"from":last,"to":current})
                previous[c["id"]]=current
        result["first_parent_history"] = {
            "since_utc":since,"commits_scanned":len(commits),
            "first":commits[0] if commits else None,
            "last":commits[-1] if commits else None,
            "claims_flipped":sum(bool(t) for t in transitions.values()),
            "transitions":{k:v for k,v in transitions.items() if v}
        }
    return result

if __name__ == "__main__":
    if len(sys.argv)!=4:
        raise SystemExit("usage: phase2_audit.py REPO CLAIMS_JSON OUTPUT_JSON")
    repo=Path(sys.argv[1]).resolve()
    claims=Path(sys.argv[2]).resolve()
    out=Path(sys.argv[3]).resolve()
    if out.exists():
        raise SystemExit("refusing to overwrite existing output")
    result=run(repo,claims,history=True)
    out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"output":str(out),"summaries":{p:v["summary"] for p,v in result["pins"].items()},
                      "mutation":{"eligible":result["mutation_at_head"]["eligible"],"killed":result["mutation_at_head"]["killed"],
                                  "survivors":result["mutation_at_head"]["survivors"]},
                      "history":{"commits_scanned":result["first_parent_history"]["commits_scanned"],
                                 "claims_flipped":result["first_parent_history"]["claims_flipped"],
                                 "transitions":result["first_parent_history"]["transitions"]}},indent=2))
