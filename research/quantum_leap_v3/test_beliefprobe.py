import importlib.util,json,subprocess,tempfile,unittest,sys
from pathlib import Path
p=Path(__file__).with_name("beliefprobe.py")
spec=importlib.util.spec_from_file_location("ql_probe",p)
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        def git(*x): subprocess.run(["git","-C",str(self.root),*x],check=True,capture_output=True)
        git("init","-q");git("config","user.name","Fixture");git("config","user.email","test@example.invalid")
        (self.root/"api.py").write_text("def outer():\n    def secret(): pass\ndef public(): pass\n")
        (self.root/"schema.json").write_text(json.dumps({"$defs":{"Open":{"properties":{},"additionalProperties":True},"Closed":{"properties":{},"additionalProperties":False}}}))
        (self.root/"lines.txt").write_text("one\ntwo")
        git("add",".");git("commit","-qm","fixture")
        self.tree=m.Tree(str(self.root),"HEAD")
    def check(self,kind,args):return m.evaluate(self.tree,{"kind":kind,"args":args})
    def test_nested_scope(self):
        self.assertEqual(self.check("symbol_defined",{"path":"api.py","name":"secret"})["predicate_status"],m.EXCEEDS)
        self.assertEqual(self.check("symbol_defined",{"path":"api.py","name":"secret","scope":"any"})["predicate_status"],m.WITHIN)
    def test_schema_closed_requirement(self):
        self.assertEqual(self.check("schema_property_absent",{"path":"schema.json","def":"Open","regex":"attest"})["predicate_status"],m.INCONCLUSIVE)
        self.assertEqual(self.check("schema_property_absent",{"path":"schema.json","def":"Closed","regex":"attest"})["predicate_status"],m.WITHIN)
    def test_invalid_regex(self):
        self.assertEqual(self.check("pattern_count",{"glob":"api.py","regex":"[","op":">=","n":1})["predicate_status"],m.INCONCLUSIVE)
    def test_pinned_git_read(self):
        (self.root/"api.py").write_text("TAMPERED")
        self.assertEqual(self.check("pattern_count",{"glob":"api.py","regex":"TAMPERED","op":"==","n":0})["predicate_status"],m.WITHIN)
    def test_line_convention(self):
        a={"glob":"lines.txt","op":"==","n":2}
        self.assertEqual(self.check("line_total",a)["predicate_status"],m.WITHIN)
        self.assertEqual(self.check("line_total",dict(a,n=1,convention="wc-l"))["predicate_status"],m.WITHIN)
    def test_within_never_promoted(self):
        result=self.check("symbol_defined",{"path":"api.py","name":"public"})
        self.assertEqual(result["predicate_status"],m.WITHIN)
        self.assertFalse(result["promotion_eligible"])
        self.assertEqual(result["semantic_entailment"],"NOT_ASSESSED")
    def test_missing_source_inconclusive(self):
        self.assertEqual(self.check("symbol_defined",{"path":"missing.py","name":"public"})["predicate_status"],m.INCONCLUSIVE)
    def test_unknown_kind_unsupported(self):
        self.assertEqual(self.check("magic",{})["predicate_status"],m.UNSUPPORTED)

    def probe(self, kind, args):
        return m.evaluate(self.tree, {"kind":kind,"args":args})
    def test_symbol_at_line_define_and_mention(self):
        self.assertEqual(self.probe("symbol_at_line",{"path":"api.py","name":"outer","line":1})["predicate_status"],m.WITHIN)
        self.assertEqual(self.probe("symbol_at_line",{"path":"api.py","name":"outer","line":2})["predicate_status"],m.EXCEEDS)
        self.assertEqual(self.probe("symbol_at_line",{"path":"api.py","name":"secret","line":2,"form":"mention"})["predicate_status"],m.WITHIN)
    def test_collection_size_literal(self):
        (self.root/"collection.py").write_text("COL = frozenset({'a','b'})\n")
        subprocess.run(["git","-C",str(self.root),"add","."],check=True,capture_output=True)
        subprocess.run(["git","-C",str(self.root),"commit","-qm","fixture collection"],check=True,capture_output=True)
        tree=m.Tree(str(self.root),"HEAD")
        self.assertEqual(m.evaluate(tree,{"kind":"collection_size","args":{"path":"collection.py","name":"COL","op":"==","n":2}})["predicate_status"],m.WITHIN)
    def test_collection_size_unknown_constructor(self):
        (self.root/"collection.py").write_text("COL = unknown_constructor(['a','b'])\n")
        subprocess.run(["git","-C",str(self.root),"add","."],check=True,capture_output=True)
        subprocess.run(["git","-C",str(self.root),"commit","-qm","fixture dynamic"],check=True,capture_output=True)
        tree=m.Tree(str(self.root),"HEAD")
        self.assertEqual(m.evaluate(tree,{"kind":"collection_size","args":{"path":"collection.py","name":"COL","op":"==","n":2}})["predicate_status"],m.INCONCLUSIVE)
    def test_permitted_outputs_never_authorize_claims(self):
        claims_path=HERE/"claims_v3_original.json" if "HERE" in globals() else p.with_name("claims_v3_original.json")
        self.assertEqual(len(json.loads(claims_path.read_text())),52)
        for c in json.loads(claims_path.read_text()):
            if c["kind"] is None: continue
            result=m.evaluate(self.tree,c)
            self.assertFalse(result["promotion_eligible"])
            self.assertEqual(result["semantic_entailment"],"NOT_ASSESSED")

if __name__=="__main__":unittest.main(verbosity=2)
