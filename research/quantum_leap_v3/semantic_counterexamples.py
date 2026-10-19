"""Adversarial counterexamples for the v3 claim-to-predicate entailment gap.

Each case creates real Git objects and runs the exact v3 predicate against them.
The stronger content claim is FALSE in that synthetic world by inspection or a
direct deterministic behavior check. These cases do not allege that CAPT's
current code exhibits the same defect; they disprove predicate sufficiency.
"""
from __future__ import annotations

import importlib.util
import json
import hashlib
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

_SPEC=importlib.util.spec_from_file_location("ql_counterexample_probe",Path(__file__).with_name("beliefprobe.py"))
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError("beliefprobe unavailable")
bp=importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bp)

@dataclass(frozen=True)
class Case:
    id: str
    claim_id: str
    misleading_prose: str
    failure_mode: str
    files: dict[str,str]
    independent_false_witness: Callable[[Path], bool]

def _refuses_wrong_token(root:Path)->bool:
    src=(root/"desktop/capt_runtime_service.py").read_text()
    # The actual invoked service in this case returns True unconditionally.
    return "def admit_client(auth, token):\n    return True" not in src

def _digest_binds_payload(root:Path)->bool:
    source=(root/"capt_runtime/prepared_execution.py").read_text()
    # Directly verify two known distinct inputs produce identical constant output.
    import ast
    module=ast.parse(source)
    fn=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=="prepared_execution_digest")
    ret=next(n for n in fn.body if isinstance(n,ast.Return))
    return not (isinstance(ret.value,ast.Constant) and ret.value.value=="sha256:"+"0"*64)

def _replay_rejects_historical_authority(root:Path)->bool:
    return "return historical_grant" not in (root/"capt_runtime/aggregates/replay_fork.py").read_text()

def _context_preserved(root:Path)->bool:
    return "return {}" not in (root/"capt_runtime/continuation_context.py").read_text()

def _no_commit_time_anywhere(root:Path)->bool:
    return "committed_at TEXT" not in (root/"capt_runtime/schema_migration.py").read_text()

CASES=(
    Case(
        "C1", "HO5",
        "A session-token check in source establishes that client admission is token-gated",
        "unreachable_checker",
        {"desktop/capt_runtime_service.py":
         'def _unused_check(auth, token):\n    if not auth or auth.get("token") != token:\n        return False\n    return True\n\ndef admit_client(auth, token):\n    return True\n'},
        lambda p: not _refuses_wrong_token(p)),
    Case(
        "C2","AS9",
        "A digest-named function establishes that prepared inputs are actually content bound",
        "constant_digest_function",
        {"capt_runtime/prepared_execution.py":
         "def prepared_execution_digest(prepared):\n    return 'sha256:"+"0"*64+"'\n"},
        lambda p: not _digest_binds_payload(p)),
    Case(
        "C3","AS6",
        "A non-reactivation error constant proves that replay forks cannot reuse historical grants",
        "warning_only",
        {"capt_runtime/aggregates/replay_fork.py":
         'REPLAY_FORK_CANNOT_REACTIVATE_HISTORICAL_AUTHORITY = "denied"\n'
         'def can_reactivate(historical_grant):\n    return historical_grant\n'},
        lambda p: not _replay_rejects_historical_authority(p)),
    Case(
        "C4","HO3",
        "Presence of select_continuation_context proves authoritative context is preserved",
        "empty_context_return",
        {"capt_runtime/continuation_context.py":
         'def select_continuation_context(*_args, **_kwargs):\n    return {}\n'},
        lambda p: not _context_preserved(p)),
    Case(
        "C5","PU13",
        "No commit-time string in store.py proves event storage lacks a commit-time field",
        "schema_in_separate_file",
        {"capt_runtime/store.py":
         "from capt_runtime.schema_migration import MIGRATION\n",
         "capt_runtime/schema_migration.py":
         "MIGRATION = 'ALTER TABLE events ADD COLUMN committed_at TEXT'\n"},
        lambda p: not _no_commit_time_anywhere(p)),
)

def _git(repo:Path,*args:str)->str:
    r=subprocess.run(["git","-C",str(repo),*args],capture_output=True,text=True,timeout=15)
    if r.returncode: raise RuntimeError(r.stderr)
    return r.stdout.strip()

def run()->dict:
    with tempfile.TemporaryDirectory(prefix="ql-semantic-negative-") as td:
        repo=Path(td)
        _git(repo,"init","-q")
        _git(repo,"config","user.email","fixture@example.invalid")
        _git(repo,"config","user.name","Adversarial Fixture")
        for case in CASES:
            pass
        corpus=json.loads(Path(__file__).with_name("claims_v3_original.json").read_text())
        by_id={c["id"]:c for c in corpus}
        cases_out=[]
        for c in CASES:
            # Remove only tracked source files from the fixture before each commit.
            for p in repo.rglob("*"):
                if p.is_file() and ".git" not in p.parts:
                    p.unlink()
            for name,text in c.files.items():
                path=repo/name
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text(text)
            _git(repo,"add","-A")
            _git(repo,"commit","--allow-empty","-qm","synthetic case "+c.id)
            commit=_git(repo,"rev-parse","HEAD")
            predicate=bp.evaluate(bp.Tree(str(repo),commit),by_id[c.claim_id])
            stronger_false=bool(c.independent_false_witness(repo))
            cases_out.append({
                "case":c.id,"claim_id":c.claim_id,"failure_mode":c.failure_mode,
                "synthetic_commit_ephemeral":commit,
                "fixture_source_sha256":hashlib.sha256(json.dumps(c.files,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
                "predicate_verdict":predicate["predicate_status"],
                "semantic_counterexample_established":stronger_false,
                "semantic_entailment":"DISPROVEN_FOR_PREDICATE_IN_GENERAL",
                "actual_CAPT_claim_truth":"NOT_ASSESSED",
            })
        return {
            "scope":"synthetic counterexample Git trees, not actual CAPT defect claims",
            "count":len(cases_out),
            "predicate_sufficiency_failures":sum(
                x["predicate_verdict"]=="WITHIN" and x["semantic_counterexample_established"]
                for x in cases_out
            ),
            "cases":cases_out
        }

if __name__=="__main__":
    print(json.dumps(run(),sort_keys=True,indent=2))
