"""Real negative-control Git repositories built and evaluated per test run."""
import importlib.util
import sys
import unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location("ql_semantic_negative",Path(__file__).with_name("semantic_counterexamples.py"))
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)
class SemanticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result=m.run()
    def test_all_cases_construct_real_git_history(self):
        self.assertEqual(len(self.result["cases"]),5)
        self.assertTrue(all(len(c["synthetic_commit_ephemeral"])==40 for c in self.result["cases"]))
    def test_all_probes_satisfied_despite_false_claim(self):
        for case in self.result["cases"]:
            with self.subTest(case=case["case"]):
                self.assertEqual(case["predicate_verdict"],"WITHIN")
                self.assertTrue(case["semantic_counterexample_established"])
                self.assertEqual(case["actual_CAPT_claim_truth"],"NOT_ASSESSED")
    def test_no_historical_truth_claim_inferred(self):
        self.assertEqual(self.result["predicate_sufficiency_failures"],5)
        self.assertIn("synthetic",self.result["scope"])
if __name__=="__main__":
    unittest.main(verbosity=2)
