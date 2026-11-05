"""Read-only, shadow-only Certainty Debt Ratchet for an unadjudicated claim corpus.

Consumes immutable phase2 results. It NEVER grants authority, claims semantic
verification, or makes a real release decision. No live CAPT service import.
"""
from __future__ import annotations
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

class RatchetInputError(ValueError):
    pass

@dataclass(frozen=True)
class ShadowVerdict:
    baseline_commit: str
    candidate_commit: str
    baseline_debt: int
    candidate_debt: int
    debt_delta: int
    new_unconfirmed: tuple[str, ...]
    newly_cleared: tuple[str, ...]
    state: str
    semantic_verification: str = "NOT_ASSESSED"
    runtime_release_authorized: bool = False
    def as_dict(self) -> dict[str, Any]:
        return {
            "baseline_commit": self.baseline_commit,
            "candidate_commit": self.candidate_commit,
            "baseline_D_proxy": self.baseline_debt,
            "candidate_D_proxy": self.candidate_debt,
            "D_proxy_delta": self.debt_delta,
            "new_unconfirmed": list(self.new_unconfirmed),
            "newly_cleared": list(self.newly_cleared),
            "shadow_state": self.state,
            "semantic_verification": self.semantic_verification,
            "runtime_release_authorized": self.runtime_release_authorized,
        }

def _claims(pin: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = pin.get("claims")
    if not isinstance(rows, list) or not rows:
        raise RatchetInputError("empty or invalid claim population")
    by_id = {}
    for row in rows:
        cid = row.get("id")
        if not isinstance(cid,str) or not cid or cid in by_id:
            raise RatchetInputError("duplicate or invalid claim identifier")
        if row.get("fidelity") not in ("full","partial","none"):
            raise RatchetInputError("invalid fidelity label")
        if row.get("predicate_status") not in ("WITHIN","EXCEEDS","UNSUPPORTED","INCONCLUSIVE"):
            raise RatchetInputError("unknown predicate verdict")
        if row.get("semantic_entailment") != "NOT_ASSESSED" or row.get("promotion_eligible") is not False:
            raise RatchetInputError("semantic-promotion invariant violated")
        by_id[cid]=row
    return by_id

def assess(audit: Mapping[str,Any], baseline: str, candidate: str) -> ShadowVerdict:
    if not isinstance(audit,Mapping) or not audit.get("D_proxy_is_not_semantic_certainty_debt"):
        raise RatchetInputError("missing explicit proxy limitation")
    if audit.get("promotion_eligible") is not False:
        raise RatchetInputError("unexpected promotion eligibility")
    pins=audit.get("pins")
    if not isinstance(pins,Mapping) or baseline not in pins or candidate not in pins:
        raise RatchetInputError("missing pin")
    a,b=pins[baseline],pins[candidate]
    ca,cb=_claims(a),_claims(b)
    if ca.keys()!=cb.keys():
        raise RatchetInputError("claim population changed; no valid longitudinal comparison")
    if any(ca[k]["fidelity"]!=cb[k]["fidelity"] for k in ca):
        raise RatchetInputError("fidelity reclassification requires separately reviewed migration")
    if not all(isinstance(pin.get("sha"),str) and len(pin["sha"])==40 for pin in (a,b)):
        raise RatchetInputError("missing canonical Git object identities")
    def unconfirmed(c):
        return {k for k,v in c.items() if v["fidelity"]!="full" or v["predicate_status"]!="WITHIN"}
    da,db=unconfirmed(ca),unconfirmed(cb)
    delta=len(db)-len(da)
    # This is an advisory signal, not an enforceable release gate.
    state="WOULD_PAUSE_FOR_REVIEW" if delta>0 else "NO_DEBT_INCREASE_OBSERVED"
    return ShadowVerdict(
        a["sha"],b["sha"],len(da),len(db),delta,
        tuple(sorted(db-da)),tuple(sorted(da-db)),state
    )

def run_file(path: Path, baseline: str, candidate: str, output: Path) -> ShadowVerdict:
    if output.exists():
        raise RatchetInputError("refusing to overwrite evidence")
    raw=path.read_bytes()
    audit=json.loads(raw)
    result=assess(audit,baseline,candidate)
    payload={
        "source_results_sha256":hashlib.sha256(raw).hexdigest(),
        "scope":"advisory; D_proxy only; NOT a production gate",
        **result.as_dict(),
    }
    output.write_text(json.dumps(payload,sort_keys=True,indent=2)+"\n")
    return result

if __name__=="__main__":
    if len(sys.argv)!=5:
        raise SystemExit("usage: shadow_ratchet.py phase2_results.json BASELINE_PIN CANDIDATE_PIN OUTPUT.json")
    verdict=run_file(Path(sys.argv[1]),sys.argv[2],sys.argv[3],Path(sys.argv[4]))
    print(json.dumps(verdict.as_dict(),indent=2))
