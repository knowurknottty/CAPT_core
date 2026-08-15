"""Bounded, untrusted provider ExecutionDriver for CAPT governed work orders."""
from __future__ import annotations
import asyncio, hashlib, json, time, urllib.error, urllib.request
from pathlib import Path
from typing import Any, Dict

from ..ingestion import IngestionRejection

DRIVER_ID = "provider"
DESCRIPTOR = {"schemaVersion":"1.0.0","driverId":DRIVER_ID,"driverVersion":"0.1.0","supportedOperations":["submit","inspect","cancel","resume","reconcile"],"writeCapable":False}

class ProviderDriverFailure(RuntimeError): pass

class ProviderDriver:
    KIND = DRIVER_ID
    def __init__(self, staging_root: str, *, provider_id: str, model: str, base_url: str, api_key: str = "", task_resolver=None):
        self.root=Path(staging_root); self.root.mkdir(parents=True, exist_ok=True)
        self.provider_id,self.model,self.base_url,self.api_key,self.task_resolver=provider_id,model,base_url.rstrip("/"),api_key,task_resolver
        self.runs: Dict[str,Dict[str,Any]]={}
    def describe(self): return dict(DESCRIPTOR)
    async def submit(self, work_order):
        rid=work_order["driverRunId"]
        if rid in self.runs: raise ProviderDriverFailure("duplicate driverRunId")
        self.runs[rid]={"state":"running"}
        return await asyncio.to_thread(self._execute,rid,work_order)
    async def inspect(self,rid): return {"driverRunId":rid,"state":self.runs.get(rid,{}).get("state","unknown")}
    async def cancel(self,rid,reason): self.runs[rid]["state"]="cancelled"
    async def resume(self,rid,resume_input=None): raise ProviderDriverFailure("provider runs are not resumable")
    async def reconcile(self,rid): return {"driverRunId":rid,"result":"external_state_unknown","anomalies":[]}
    def _execute(self,rid,wo):
        prompt = self.task_resolver.resolve_for_execution(mission_id=wo["missionId"], task_id=wo["taskId"]).objective if self.task_resolver else "Provide a bounded evidence-backed observation."
        prompt_digest="sha256:"+hashlib.sha256(prompt.encode()).hexdigest()
        headers={"Content-Type":"application/json","Accept":"application/json"}
        if self.api_key: headers["Authorization"]="Bearer "+self.api_key
        if self.provider_id=="ollama":
            url=self.base_url.replace("/v1","")+"/api/generate"; body={"model":self.model,"prompt":prompt,"stream":False}
        else:
            url=self.base_url+"/chat/completions"; body={"model":self.model,"messages":[{"role":"user","content":prompt}],"stream":False}
        try:
            req=urllib.request.Request(url,data=json.dumps(body).encode(),headers=headers,method="POST")
            with urllib.request.urlopen(req,timeout=120) as r: data=json.loads(r.read().decode())
        except urllib.error.HTTPError as e: raise ProviderDriverFailure("provider HTTP %s"%e.code) from e
        except Exception as e: raise ProviderDriverFailure("provider unavailable: %s"%type(e).__name__) from e
        text=(data.get("response") if self.provider_id=="ollama" else ((data.get("choices") or [{}])[0].get("message",{}).get("content"))) or ""
        if not text: raise ProviderDriverFailure("provider returned no content")
        response_digest="sha256:"+hashlib.sha256(text.encode()).hexdigest()
        artifact=("# CAPT Provider Observation\n\nProvider: %s\nModel: %s\nEndpointClass: %s\nPromptDigest: %s\nResponseDigest: %s\n\n%s\n"%(self.provider_id,self.model,"local" if self.provider_id=="ollama" else "cloud",prompt_digest,response_digest,text))
        p=self.root/("provider-analysis-%s.md"%rid); p.write_text(artifact)
        digest="sha256:"+hashlib.sha256(artifact.encode()).hexdigest()
        self.runs[rid]["state"]="completed"
        return {"driverRunId":rid,"externalRunId":"%s-%s"%(self.provider_id,rid),"state":"running","observations":[{"schemaVersion":"1.0.0","observationId":"obs-"+rid,"observedBy":DRIVER_ID,"trust":"untrusted","workOrderId":rid,"summary":text[:8192],"observedAt":wo.get("submittedAt","")}],"artifactCandidate":{"schemaVersion":"1.0.0","candidateId":"ac-"+rid,"driverRunId":rid,"artifactPath":str(p),"artifactDigest":digest,"producedAt":wo.get("submittedAt","")},"diagnostics":{"provider":self.provider_id,"model":self.model,"endpointClass":"local" if self.provider_id=="ollama" else "cloud","promptDigest":prompt_digest,"responseDigest":response_digest}}