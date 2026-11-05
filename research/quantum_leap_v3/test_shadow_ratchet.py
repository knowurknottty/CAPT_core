"""Tests use the actual 52-claim evidence file; no simulated provider or authority."""
import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).parent
spec=importlib.util.spec_from_file_location("ql_ratchet",ROOT/"shadow_ratchet.py")
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)
class RatchetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((ROOT/"phase2_results.json").read_text())
    def test_real_head_increases_proxy_debt(self):
        v=m.assess(self.data,"3f11800","e28b665")
        self.assertEqual((v.baseline_debt,v.candidate_debt,v.debt_delta),(19,20,1))
        self.assertEqual(v.new_unconfirmed,("PU7",))
        self.assertEqual(v.state,"WOULD_PAUSE_FOR_REVIEW")
        self.assertFalse(v.runtime_release_authorized)
    def test_same_commit_not_pause(self):
        v=m.assess(self.data,"e28b665","e28b665")
        self.assertEqual(v.debt_delta,0)
        self.assertEqual(v.state,"NO_DEBT_INCREASE_OBSERVED")
    def test_missing_claim_population_blocks_comparison(self):
        a=copy.deepcopy(self.data)
        a["pins"]["e28b665"]["claims"].pop()
        with self.assertRaises(m.RatchetInputError):
            m.assess(a,"3f11800","e28b665")
    def test_fidelity_changes_block_comparison(self):
        a=copy.deepcopy(self.data)
        a["pins"]["e28b665"]["claims"][0]["fidelity"]="full"
        with self.assertRaises(m.RatchetInputError):
            m.assess(a,"3f11800","e28b665")
    def test_missing_promotion_boundary_refused(self):
        a=copy.deepcopy(self.data)
        a["promotion_eligible"]=True
        with self.assertRaises(m.RatchetInputError):
            m.assess(a,"3f11800","e28b665")
    def test_incorrect_semantic_flag_refused(self):
        a=copy.deepcopy(self.data)
        a["pins"]["e28b665"]["claims"][0]["semantic_entailment"]="VERIFIED"
        with self.assertRaises(m.RatchetInputError):
            m.assess(a,"3f11800","e28b665")
    def test_overwrite_refused(self):
        with tempfile.TemporaryDirectory() as td:
            target=Path(td)/"output.json"
            source=ROOT/"phase2_results.json"
            m.run_file(source,"3f11800","e28b665",target)
            with self.assertRaises(m.RatchetInputError):
                m.run_file(source,"3f11800","e28b665",target)
    def test_original_source_unchanged(self):
        raw=(ROOT/"phase2_results.json").read_bytes()
        m.assess(self.data,"c5b6f6a","e28b665")
        self.assertEqual(raw,(ROOT/"phase2_results.json").read_bytes())

if __name__=="__main__":unittest.main(verbosity=2)
