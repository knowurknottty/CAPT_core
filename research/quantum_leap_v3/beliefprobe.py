"""Read-only pinned Git claim predicates. No CAPT authority or claim promotion.

WITHIN validates only the encoded predicate, never semantic entailment of prose.
"""
from __future__ import annotations
import ast, fnmatch, json, re, signal, subprocess, sys
from pathlib import Path

WITHIN,EXCEEDS,UNSUPPORTED,INCONCLUSIVE=("WITHIN","EXCEEDS","UNSUPPORTED","INCONCLUSIVE")

class ProbeError(Exception): pass

def git(repo,*args):
    try: p=subprocess.run(["git","-C",repo,*args],capture_output=True,timeout=15)
    except (OSError,subprocess.TimeoutExpired) as e: raise ProbeError("git unavailable or timed out") from e
    if p.returncode: raise ProbeError("git command failed: "+p.stderr.decode("utf-8","replace")[:100])
    if len(p.stdout)>4_000_000: raise ProbeError("git object too large")
    try: return p.stdout.decode("utf-8")
    except UnicodeDecodeError as e: raise ProbeError("non-UTF8 source") from e

class Tree:
    def __init__(self,repo,commit):
        self.repo=repo
        self.commit=git(repo,"rev-parse","--verify",commit+"^{commit}").strip()
        self._paths=None
    def paths(self):
        if self._paths is None: self._paths=git(self.repo,"ls-tree","-r","--name-only",self.commit).splitlines()
        return self._paths
    def read(self,path):
        if not isinstance(path,str) or path.startswith("/") or ".." in Path(path).parts: raise ProbeError("invalid path")
        if path not in self.paths(): raise ProbeError("missing pinned path: "+path)
        size=int(git(self.repo,"cat-file","-s",self.commit+":"+path))
        if size>1_000_000: raise ProbeError("source file over budget")
        return git(self.repo,"show",self.commit+":"+path)

def expression(text):
    if not isinstance(text,str) or len(text)>400: raise ProbeError("regex over budget")
    try: return re.compile(text,re.MULTILINE)
    except re.error as e: raise ProbeError("invalid regex: "+str(e)) from e

def match_paths(tree,args):
    paths=[p for p in tree.paths() if fnmatch.fnmatch(p,args["glob"]) and not any(fnmatch.fnmatch(p,e) for e in args.get("exclude",[]))]
    if not paths: raise ProbeError("empty matched path set")
    if len(paths)>400: raise ProbeError("too many matching files")
    return paths

def evaluate_inner(tree,c):
    kind=c.get("kind"); a=c.get("args") or {}
    if kind=="symbol_defined":
        kind_want=a.get("kind","any"); scope=a.get("scope","module")
        if kind_want not in ("any","function","class") or scope not in ("module","any"): raise ProbeError("invalid scope/kind")
        module=ast.parse(tree.read(a["path"]))
        nodes=module.body if scope=="module" else ast.walk(module)
        names=[n.name for n in nodes if (isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and kind_want in ("any","function")) or (isinstance(n,ast.ClassDef) and kind_want in ("any","class"))]
        ok=a["name"] in names
        return WITHIN if ok else EXCEEDS,"symbol "+("found" if ok else "missing")+" in "+scope+" scope"
    if kind=="schema_property_absent":
        doc=json.loads(tree.read(a["path"]))
        definition=(doc.get("$defs") or doc.get("definitions") or {}).get(a["def"])
        if not isinstance(definition,dict): raise ProbeError("missing schema definition")
        props=definition.get("properties",{})
        if not isinstance(props,dict): raise ProbeError("invalid schema properties")
        hits=[k for k in props if expression(a["regex"]).search(k)]
        if hits: return EXCEEDS,"declared property "+str(hits)
        if definition.get("additionalProperties") is not False or any(k in definition for k in ("allOf","anyOf","oneOf","$ref","patternProperties","unevaluatedProperties")):
            raise ProbeError("schema shape open or composed, absence not proven")
        return WITHIN,"matching property absent in simple closed definition"
    if kind=="pattern_count":
        paths=match_paths(tree,a); r=expression(a["regex"])
        n=sum(len(r.findall(tree.read(p))) for p in paths)
    elif kind=="file_count":
        paths=match_paths(tree,a); n=len(paths)
    elif kind=="line_total":
        paths=match_paths(tree,a)
        conv=a.get("convention","splitlines")
        if conv not in ("splitlines","wc-l"): raise ProbeError("invalid line convention")
        n=sum(len(tree.read(p).splitlines()) if conv=="splitlines" else tree.read(p).count("\n") for p in paths)
    elif kind=="path_exists":
        ok=a["path"] in tree.paths()
        return WITHIN if ok else EXCEEDS,"path existence="+str(ok)
    else: return UNSUPPORTED,"unsupported predicate"
    ops={"==":lambda x,y:x==y,">=":lambda x,y:x>=y,"<=":lambda x,y:x<=y,">":lambda x,y:x>y,"<":lambda x,y:x<y}
    if a["op"] not in ops: raise ProbeError("bad comparison operator")
    ok=ops[a["op"]](n,int(a["n"]))
    return WITHIN if ok else EXCEEDS,"count="+str(n)

def evaluate(tree,c):
    if c.get("kind") not in ("symbol_defined","schema_property_absent","pattern_count","file_count","line_total","path_exists"):
        return {"predicate_status":UNSUPPORTED,"detail":"unsupported predicate","semantic_entailment":"NOT_ASSESSED","promotion_eligible":False}
    def timeout(_signum,_frame): raise ProbeError("evaluation timeout")
    if not hasattr(signal,"setitimer"): raise RuntimeError("POSIX signal budget required")
    old=signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM,timeout)
    signal.setitimer(signal.ITIMER_REAL,8)
    try:
        try: status,detail=evaluate_inner(tree,c)
        except (ProbeError,KeyError,ValueError,TypeError,OverflowError,re.error,SyntaxError,RecursionError,MemoryError) as e:
            status,detail=INCONCLUSIVE,type(e).__name__+": "+str(e)
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,old)
    return {"predicate_status":status,"detail":detail,"semantic_entailment":"NOT_ASSESSED","promotion_eligible":False}

def run(repo,claims,commit):
    tree=Tree(repo,commit)
    return {"commit":tree.commit,"scope":"read-only predicates only; no claim entailment",
            "results":[dict(id=x.get("id"),**evaluate(tree,x)) for x in claims]}

if __name__=="__main__":
    if len(sys.argv)!=4: raise SystemExit("usage: beliefprobe.py repo claims.json commit")
    with open(sys.argv[2],encoding="utf-8") as f: claims=json.load(f)
    print(json.dumps(run(sys.argv[1],claims,sys.argv[3]),indent=2))
