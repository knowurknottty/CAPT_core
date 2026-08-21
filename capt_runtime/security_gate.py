"""CAPT-native release security gate."""
from __future__ import annotations
import argparse, json
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

class Severity(str, Enum):
    CRITICAL="critical"; HIGH="high"; MEDIUM="medium"; LOW="low"

class EvidenceStatus(str, Enum):
    PASS="pass"; FAIL="fail"; NOT_VERIFIED="not_verified"

class ResultStatus(str, Enum):
    PASS="pass"; FAIL="fail"; NOT_VERIFIED="not_verified"; NOT_APPLICABLE="not_applicable"

@dataclass(frozen=True)
class SecurityControl:
    control_id: str
    title: str
    category: str
    severity: Severity
    source: str
    capabilities_any: Tuple[str,...]=()
    capabilities_all: Tuple[str,...]=()
    release_blocking: bool=True
    verification_hint: str=""
    def applies(self, capabilities:frozenset[str])->bool:
        if self.capabilities_all and not set(self.capabilities_all).issubset(capabilities): return False
        if self.capabilities_any and not set(self.capabilities_any).intersection(capabilities): return False
        return True

@dataclass(frozen=True)
class SecurityProfile:
    name: str
    capabilities: frozenset[str]
    description: str=""
    @classmethod
    def from_mapping(cls, value:Mapping[str,object])->"SecurityProfile":
        name=str(value.get("name") or "").strip()
        if not name: raise ValueError("SECURITY_PROFILE_NAME_REQUIRED")
        raw=value.get("capabilities",[])
        if not isinstance(raw,list) or not all(isinstance(x,str) and x for x in raw):
            raise ValueError("SECURITY_PROFILE_CAPABILITIES_INVALID")
        return cls(name, frozenset(raw), str(value.get("description") or ""))

@dataclass(frozen=True)
class SecurityEvidence:
    control_id:str
    status:EvidenceStatus
    source_sha:str
    refs:Tuple[str,...]
    verifier:str
    detail:str=""
    @classmethod
    def from_mapping(cls, value:Mapping[str,object])->"SecurityEvidence":
        cid=str(value.get("controlId") or "").strip()
        if not cid: raise ValueError("SECURITY_EVIDENCE_CONTROL_ID_REQUIRED")
        status=EvidenceStatus(str(value.get("status") or "not_verified"))
        sha=str(value.get("sourceSha") or "").strip()
        refs=value.get("refs",[])
        if not isinstance(refs,list) or not all(isinstance(x,str) and x for x in refs):
            raise ValueError("SECURITY_EVIDENCE_REFS_INVALID")
        verifier=str(value.get("verifier") or "").strip()
        if status in {EvidenceStatus.PASS,EvidenceStatus.FAIL}:
            if not sha: raise ValueError("SECURITY_EVIDENCE_SHA_REQUIRED")
            if not refs: raise ValueError("SECURITY_EVIDENCE_REF_REQUIRED")
            if not verifier: raise ValueError("SECURITY_EVIDENCE_VERIFIER_REQUIRED")
        return cls(cid,status,sha,tuple(refs),verifier,str(value.get("detail") or ""))

@dataclass(frozen=True)
class ControlResult:
    control_id:str; title:str; status:ResultStatus; severity:str
    release_blocking:bool; reason:str; evidence_refs:Tuple[str,...]=()

@dataclass(frozen=True)
class SecurityGateResult:
    profile:str; source_sha:str; decision:str; counts:Dict[str,int]
    blocking_controls:Tuple[str,...]; results:Tuple[ControlResult,...]
    def to_dict(self):
        return {"profile":self.profile,"sourceSha":self.source_sha,"decision":self.decision,
                "counts":dict(self.counts),"blockingControls":list(self.blocking_controls),
                "results":[{**asdict(r),"status":r.status.value,"evidence_refs":list(r.evidence_refs)} for r in self.results]}

PT1="Millee pre-launch checklist pt.1 screenshot supplied 2026-08-16"
PT2="Millee pre-launch checklist pt.2 screenshot supplied 2026-08-16"
CAPT_SUP="CAPT supplemental pre-launch controls"

def _c(cid,title,category,severity,source,*,any_caps=(),all_caps=(),hint=""):
    return SecurityControl(cid,title,category,severity,source,tuple(any_caps),tuple(all_caps),True,hint)

CONTROLS:Tuple[SecurityControl,...]=(
    _c("VIBE1-01","Hide API keys","secrets",Severity.CRITICAL,PT1,hint="secret scan + client/server boundary review"),
    _c("VIBE1-02","Purge Git secrets","secrets",Severity.CRITICAL,PT1,hint="full-history secret scan"),
    _c("VIBE1-03","Use public DB key","database",Severity.HIGH,PT1,any_caps=("client_database",)),
    _c("VIBE1-04","Enable row-level security","database",Severity.CRITICAL,PT1,any_caps=("multi_tenant_database",)),
    _c("VIBE1-05","Encrypt sensitive data","data",Severity.HIGH,PT1,any_caps=("sensitive_data","database","local_state")),
    _c("VIBE1-06","Enforce server-side auth","auth",Severity.CRITICAL,PT1,any_caps=("auth","public_api","ipc")),
    _c("VIBE1-07","Lock record access","authorization",Severity.CRITICAL,PT1,any_caps=("database","record_store")),
    _c("VIBE1-08","Block field tampering","validation",Severity.HIGH,PT1,any_caps=("api","ipc","forms")),
    _c("VIBE1-09","Secure session cookies","session",Severity.HIGH,PT1,any_caps=("cookie_session",)),
    _c("VIBE1-10","Hash passwords","auth",Severity.CRITICAL,PT1,any_caps=("password_auth",)),
    _c("VIBE1-11","Rate limit login","abuse",Severity.HIGH,PT1,any_caps=("login",)),
    _c("VIBE1-12","Add bot protection","abuse",Severity.MEDIUM,PT1,any_caps=("public_web","public_api")),
    _c("VIBE1-13","Parameterize queries","injection",Severity.CRITICAL,PT1,any_caps=("database",)),
    _c("VIBE1-14","Validate all input","validation",Severity.CRITICAL,PT1,any_caps=("api","ipc","forms","cli","file_input")),
    _c("VIBE1-15","Escape user content","output",Severity.HIGH,PT1,any_caps=("html","rich_text","templating")),
    _c("VIBE1-16","Restrict file uploads","files",Severity.HIGH,PT1,any_caps=("file_uploads",)),
    _c("VIBE1-17","Trim API responses","data_minimization",Severity.MEDIUM,PT1,any_caps=("api","ipc")),
    _c("VIBE1-18","Add security headers","transport",Severity.HIGH,PT1,any_caps=("http",)),
    _c("VIBE1-19","Force HTTPS","transport",Severity.CRITICAL,PT1,any_caps=("public_http",)),
    _c("VIBE1-20","Scan dependencies","supply_chain",Severity.HIGH,PT1,hint="dependency audit on exact release SHA"),
    _c("VIBE2-01","Add HSTS","transport",Severity.HIGH,PT2,any_caps=("public_http",)),
    _c("VIBE2-02","Add CSRF tokens","session",Severity.HIGH,PT2,any_caps=("cookie_session","browser_mutations")),
    _c("VIBE2-03","Reset sessions on password change","session",Severity.HIGH,PT2,all_caps=("password_auth","session_store")),
    _c("VIBE2-04","Expire reset links","auth",Severity.HIGH,PT2,any_caps=("password_reset",)),
    _c("VIBE2-05","Prevent user enumeration","auth",Severity.HIGH,PT2,any_caps=("login","password_reset")),
    _c("VIBE2-06","Whitelist upload types","files",Severity.HIGH,PT2,any_caps=("file_uploads",)),
    _c("VIBE2-07","Verify payment webhooks","payments",Severity.CRITICAL,PT2,any_caps=("payments",)),
    _c("VIBE2-08","Set prices server-side","payments",Severity.CRITICAL,PT2,any_caps=("payments",)),
    _c("VIBE2-09","Block prompt injection","ai",Severity.HIGH,PT2,any_caps=("ai","prompt_processing")),
    _c("VIBE2-10","Cap AI usage","resource_governance",Severity.HIGH,PT2,any_caps=("ai",)),
    _c("VIBE2-11","Limit request size","resource_governance",Severity.HIGH,PT2,any_caps=("api","ipc","file_uploads")),
    _c("VIBE2-12","Rate limit password resets","abuse",Severity.HIGH,PT2,any_caps=("password_reset",)),
    _c("VIBE2-13","Sanitize before storing","validation",Severity.HIGH,PT2,any_caps=("database","record_store","local_state")),
    _c("VIBE2-14","Lock down CORS","transport",Severity.HIGH,PT2,any_caps=("browser_api",)),
    _c("VIBE2-15","Disable directory listing","files",Severity.MEDIUM,PT2,any_caps=("http_file_server",)),
    _c("VIBE2-16","Remove default admin routes","attack_surface",Severity.HIGH,PT2,any_caps=("admin_routes","public_web")),
    _c("VIBE2-17","Lock accounts after failed logins","auth",Severity.MEDIUM,PT2,any_caps=("login",)),
    _c("VIBE2-18","Log security events","observability",Severity.HIGH,PT2,hint="security-relevant denials/violations must emit auditable events"),
    _c("VIBE2-19","Set secure cookie flags","session",Severity.HIGH,PT2,any_caps=("cookie_session",)),
    _c("VIBE2-20","Restrict database permissions","database",Severity.CRITICAL,PT2,any_caps=("database",)),
    _c("CAPT-SUP-01","Authorize every mutation at the authoritative boundary","authorization",Severity.CRITICAL,CAPT_SUP,any_caps=("api","ipc","database")),
    _c("CAPT-SUP-02","Keep private storage private by default","data",Severity.CRITICAL,CAPT_SUP,any_caps=("object_storage","file_uploads")),
    _c("CAPT-SUP-03","Reject malformed or expired authentication tokens","auth",Severity.CRITICAL,CAPT_SUP,any_caps=("auth",)),
    _c("CAPT-SUP-04","Minimize privileged/debug data crossing into clients","data_minimization",Severity.HIGH,CAPT_SUP,any_caps=("browser","api","ipc")),
    _c("CAPT-SUP-05","Test denied-access cases, not only happy paths","verification",Severity.HIGH,CAPT_SUP,any_caps=("auth","database","api","ipc")),
    _c("CAPT-SUP-06","Treat AI-generated/security-sensitive output as untrusted until verified","ai",Severity.HIGH,CAPT_SUP,any_caps=("ai","prompt_processing")),
    _c("CAPT-SUP-07","Set billing caps and alerts on every paid service","resource_governance",Severity.HIGH,CAPT_SUP,any_caps=("paid_service",),hint="provider-side hard billing cap plus independent spend alert evidence"),
)
CONTROL_BY_ID={c.control_id:c for c in CONTROLS}
if len(CONTROL_BY_ID)!=len(CONTROLS): raise RuntimeError("SECURITY_CONTROL_ID_DUPLICATE")

def evaluate_security_gate(profile:SecurityProfile,evidence:Iterable[SecurityEvidence],*,source_sha:str)->SecurityGateResult:
    if not source_sha: raise ValueError("SECURITY_SOURCE_SHA_REQUIRED")
    ev={}
    for item in evidence:
        if item.control_id not in CONTROL_BY_ID: raise ValueError("SECURITY_EVIDENCE_UNKNOWN_CONTROL:%s"%item.control_id)
        if item.control_id in ev: raise ValueError("SECURITY_EVIDENCE_DUPLICATE:%s"%item.control_id)
        ev[item.control_id]=item
    results=[]; blocking=[]; counts={s.value:0 for s in ResultStatus}
    for control in CONTROLS:
        if not control.applies(profile.capabilities):
            r=ControlResult(control.control_id,control.title,ResultStatus.NOT_APPLICABLE,control.severity.value,control.release_blocking,"profile capabilities do not expose this control surface")
        else:
            item=ev.get(control.control_id)
            if item is None or item.status==EvidenceStatus.NOT_VERIFIED:
                r=ControlResult(control.control_id,control.title,ResultStatus.NOT_VERIFIED,control.severity.value,control.release_blocking,"applicable control has no current verification evidence",() if item is None else item.refs)
            elif item.source_sha!=source_sha:
                r=ControlResult(control.control_id,control.title,ResultStatus.NOT_VERIFIED,control.severity.value,control.release_blocking,"evidence is stale: %s != %s"%(item.source_sha,source_sha),item.refs)
            elif item.status==EvidenceStatus.FAIL:
                r=ControlResult(control.control_id,control.title,ResultStatus.FAIL,control.severity.value,control.release_blocking,item.detail or "control verification failed",item.refs)
            else:
                r=ControlResult(control.control_id,control.title,ResultStatus.PASS,control.severity.value,control.release_blocking,item.detail or "verified at exact source SHA",item.refs)
        counts[r.status.value]+=1
        if r.release_blocking and r.status in {ResultStatus.FAIL,ResultStatus.NOT_VERIFIED}: blocking.append(r.control_id)
        results.append(r)
    return SecurityGateResult(profile.name,source_sha,"PASS" if not blocking else "BLOCKED",counts,tuple(blocking),tuple(results))

def _load_json(path:Path)->object: return json.loads(path.read_text(encoding="utf-8"))
def load_profile(path:Path)->SecurityProfile:
    raw=_load_json(path)
    if not isinstance(raw,dict): raise ValueError("SECURITY_PROFILE_INVALID")
    return SecurityProfile.from_mapping(raw)
def load_evidence(path:Path)->List[SecurityEvidence]:
    raw=_load_json(path)
    if not isinstance(raw,dict): raise ValueError("SECURITY_EVIDENCE_INVALID")
    items=raw.get("evidence",[])
    if not isinstance(items,list): raise ValueError("SECURITY_EVIDENCE_LIST_INVALID")
    return [SecurityEvidence.from_mapping(x) for x in items]

def catalog_json():
    return {"schemaVersion":"1.0.0","controls":[
        {"controlId":c.control_id,"title":c.title,"category":c.category,"severity":c.severity.value,
         "source":c.source,"capabilitiesAny":list(c.capabilities_any),"capabilitiesAll":list(c.capabilities_all),
         "releaseBlocking":c.release_blocking,"verificationHint":c.verification_hint} for c in CONTROLS]}

def main(argv:Optional[Sequence[str]]=None)->int:
    parser=argparse.ArgumentParser(prog="python -m capt_runtime.security_gate")
    sub=parser.add_subparsers(dest="command",required=True)
    p=sub.add_parser("catalog"); p.add_argument("--json",action="store_true")
    p=sub.add_parser("evaluate"); p.add_argument("--profile",type=Path,required=True); p.add_argument("--evidence",type=Path,required=True); p.add_argument("--source-sha",required=True); p.add_argument("--output",type=Path)
    args=parser.parse_args(argv)
    if args.command=="catalog":
        print(json.dumps(catalog_json(),indent=2)); return 0
    result=evaluate_security_gate(load_profile(args.profile),load_evidence(args.evidence),source_sha=args.source_sha)
    text=json.dumps(result.to_dict(),indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(text+"\n",encoding="utf-8")
    print(text); return 0 if result.decision=="PASS" else 2

if __name__=="__main__": raise SystemExit(main())
