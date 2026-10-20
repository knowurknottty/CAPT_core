"""Real Git-independent negative controls for the observe-only finite proposal interface."""
import importlib.util
import math
import sys
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location("ql_finite_decision",Path(__file__).with_name("finite_decision.py"))
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)

class FiniteDecisionTests(unittest.TestCase):
    def setUp(self):
        self.contract={
            "inspect":{"risk":"read","params":{"target":{"kind":"candidate","source":"files"}}},
            "archive":{"risk":"write","params":{"tag":{"kind":"enum","values":["safe","review"]}}},
            "delete":{"risk":"destructive","params":{"confirm":{"kind":"boolean"}}},
            "write_text":{"risk":"write","params":{"text":{"kind":"free_text"}}},
        }
        self.scope=frozenset(self.contract)
        self.offering=m.compile_offering(self.contract,{"files":["h_"+"1"*32,"h_"+"2"*32]},allowed_actions=self.scope,world_digest="a"*64,policy_digest="b"*64)
        self.floors={"read":0.5,"write":0.75,"destructive":0.9}
    def eval(self,act,params,probs,digest=None):
        return m.assess_proposal(self.offering,selected=act,parameters=params,probabilities=probs,
                                 declared_offering_digest=self.offering.digest if digest is None else digest,
                                 thresholds=self.floors)
    def test_admitted_proposal_still_has_no_runtime_authority(self):
        d=self.eval("inspect",{"target":"h_"+"1"*32},{"action":0.95,"target":0.88})
        self.assertEqual(d.status,"proposal_ready_for_runtime_review")
        self.assertFalse(d.dispatch_allowed)
        self.assertFalse(d.completed)
    def test_explicit_free_text_omission(self):
        self.assertEqual(self.offering.omissions["write_text"],"text:unsupported_parameter_kind")
    def test_candidate_must_be_opaque(self):
        o=m.compile_offering(self.contract, {"files":["sensitive_filename.txt"]},
                             allowed_actions=self.scope,world_digest="a"*64,policy_digest="b"*64)
        self.assertEqual(o.omissions["inspect"],"target:nonopaque_candidate")
    def test_action_scope_restriction(self):
        o=m.compile_offering(self.contract,{"files":["h_"+"1"*32]},allowed_actions=frozenset({"inspect"}),world_digest="a"*64,policy_digest="b"*64)
        self.assertEqual(o.omissions["delete"],"not_in_observation_scope")
    def test_missing_candidates_omit_action(self):
        o=m.compile_offering(self.contract,{},allowed_actions=self.scope,world_digest="a"*64,policy_digest="b"*64)
        self.assertEqual(o.omissions["inspect"],"target:missing_finite_options")
    def test_large_candidates_never_silently_truncated(self):
        o=m.compile_offering(self.contract,{"files":["h_"+format(i,"032x") for i in range(65)]},allowed_actions=self.scope,world_digest="a"*64,policy_digest="b"*64)
        self.assertEqual(o.omissions["inspect"],"target:option_budget_exceeded")
    def test_unknown_action_refused(self):
        self.assertEqual(self.eval("phantom",{},{"action":1}).status,"refused")
    def test_unoffered_parameter_refused(self):
        self.assertEqual(self.eval("inspect",{"target":"SECRET_RAW_FILENAME"},{"action":1,"target":1}).status,"refused")
    def test_missing_probability_refused(self):
        self.assertEqual(self.eval("inspect",{"target":"h_"+"1"*32},{"action":1}).status,"refused")
    def test_nan_probability_refused(self):
        self.assertEqual(self.eval("inspect",{"target":"h_"+"1"*32},{"action":float("nan"),"target":1}).status,"refused")
    def test_bool_confidence_refused(self):
        self.assertEqual(self.eval("inspect",{"target":"h_"+"1"*32},{"action":True,"target":1}).status,"refused")
    def test_weakest_required_probability(self):
        d=self.eval("archive",{"tag":"safe"},{"action":0.99,"tag":0.70})
        self.assertEqual(d.status,"needs_escalation")
        self.assertEqual(d.weakest_probability,0.70)
    def test_stale_offering_digest_refused(self):
        self.assertEqual(self.eval("inspect",{"target":"h_"+"1"*32},{"action":1,"target":1},digest="0"*64).status,"refused")
    def test_finish_only_verification_request(self):
        d=self.eval("finish",{},{"action":1})
        self.assertEqual(d.status,"verification_required")
        self.assertFalse(d.completed)
    def test_escalate_not_exec(self):
        d=self.eval("escalate",{},{"action":1})
        self.assertEqual(d.status,"escalation_requested")
        self.assertFalse(d.dispatch_allowed)
    def test_destructive_threshold_not_permission(self):
        d=self.eval("delete",{"confirm":True},{"action":0.999,"confirm":0.998})
        self.assertEqual(d.status,"proposal_ready_for_runtime_review")
        self.assertFalse(d.dispatch_allowed)
    def test_bad_risk_unavailable(self):
        o=m.compile_offering({"surprise":{"params":{}}},{},allowed_actions=frozenset({"surprise"}),world_digest="a"*64,policy_digest="b"*64)
        self.assertEqual(o.omissions["surprise"],"missing_or_invalid_risk")
    def test_duplicate_values_omit(self):
        o=m.compile_offering({"x":{"risk":"read","params":{"p":{"kind":"enum","values":["a","a"]}}}},{},allowed_actions=frozenset({"x"}),world_digest="a"*64,policy_digest="b"*64)
        self.assertEqual(o.omissions["x"],"p:duplicate_option")
    def test_same_inputs_same_digest(self):
        o=m.compile_offering(self.contract,{"files":["h_"+"1"*32,"h_"+"2"*32]},allowed_actions=self.scope,world_digest="a"*64,policy_digest="b"*64)
        self.assertEqual(o.digest,self.offering.digest)
    def test_world_snapshot_change_invalidates_decision(self):
        old=self.offering
        newer=m.compile_offering(self.contract,{"files":["h_"+"1"*32,"h_"+"2"*32]},allowed_actions=self.scope,
                                 world_digest="c"*64,policy_digest="b"*64)
        self.assertNotEqual(old.digest,newer.digest)
        proposal=m.assess_proposal(newer, selected="inspect", parameters={"target":"h_"+"1"*32},
                                   probabilities={"action":1.0,"target":1.0},
                                   declared_offering_digest=old.digest, thresholds=self.floors)
        self.assertEqual(proposal.status,"refused")
    def test_policy_change_invalidates_decision(self):
        newer=m.compile_offering(self.contract,{"files":["h_"+"1"*32,"h_"+"2"*32]},allowed_actions=self.scope,
                                 world_digest="a"*64,policy_digest="d"*64)
        self.assertNotEqual(newer.digest,self.offering.digest)
    def test_missing_world_digest_fails_closed(self):
        with self.assertRaises(m.InvalidDecisionContract):
            m.compile_offering(self.contract,{"files":["h_"+"1"*32]},allowed_actions=self.scope,
                               world_digest="",policy_digest="b"*64)
if __name__=="__main__":
    unittest.main(verbosity=2)
