"""Uses the real CAPT ToolRequest schema and broker fingerprint, no mock services."""
import importlib.util
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from capt_runtime.tool_broker import tool_request_fingerprint
ROOT=Path(__file__).parent
def load(name):
    spec=importlib.util.spec_from_file_location("ql_"+name,ROOT/(name+".py"))
    module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    return module
f=load("finite_decision")
c=load("request_preflight")

class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.world="1"*64;self.policy="2"*64
        self.offer=f.compile_offering({"inspect":{"risk":"read","params":{"target":{"kind":"candidate","source":"available"}}}},
                                      {"available":["h_"+"3"*32]},allowed_actions=frozenset({"inspect"}),
                                      world_digest=self.world,policy_digest=self.policy)
        self.params={"target":"h_"+"3"*32}
        self.probs={"action":0.92,"target":0.91}
        self.thresholds={"read":0.5}
        self.assessment=f.assess_proposal(self.offer,selected="inspect",parameters=self.params,
                                          probabilities=self.probs,
                                          declared_offering_digest=self.offer.digest,thresholds=self.thresholds)
        self.request={
            "schemaVersion":"1.0.0",
            "toolRequestId":"ql-source-inspection-proposal",
            "toolId":"repo.read",
            "operation":"inspect",
            "arguments":[{"kind":"string","name":"target","value":self.params["target"]}],
            "consequential":False,
            "idempotencyKey":"ql-identity-regression",
            "operationFingerprint":"",
            "replayPolicy":"never",
            "requestedAt":"2026-10-19T08:00:00Z",
        }
        self.request["operationFingerprint"]=tool_request_fingerprint(self.request)
    def check(self, **kw):
        d=dict(offering=self.offer,assessment=self.assessment,selected_parameters=self.params,decision_probabilities=self.probs,
               advisory_thresholds=self.thresholds,request=self.request,expected_tool_id="repo.read",expected_operation="inspect",
               fresh_world_digest=self.world,fresh_policy_digest=self.policy)
        d.update(kw)
        return c.check_request_identity(**d)
    def test_real_contract_structural_match_is_not_authority(self):
        out=self.check()
        self.assertEqual(out["reason"],"IDENTITY_MATCH_ONLY")
        self.assertTrue(out["structural_match"])
        self.assertFalse(out["runtime_authority_verified"])
        self.assertFalse(out["dispatch_allowed"])
        self.assertFalse(out["completion_verified"])
    def test_changed_world(self):
        self.assertEqual(self.check(fresh_world_digest="4"*64)["reason"],"SOURCE_SNAPSHOT_OR_POLICY_CHANGED")
    def test_changed_policy(self):
        self.assertEqual(self.check(fresh_policy_digest="5"*64)["reason"],"SOURCE_SNAPSHOT_OR_POLICY_CHANGED")
    def test_wrong_route(self):
        self.assertEqual(self.check(expected_operation="delete")["reason"],"ROUTING_IDENTITY_MISMATCH")
    def test_tampered_fingerprint(self):
        r=dict(self.request);r["operationFingerprint"]="sha256:"+"0"*64
        self.assertEqual(self.check(request=r)["reason"],"BROKER_FINGERPRINT_MISMATCH")
    def test_extra_unoffered_arg(self):
        r=dict(self.request);r["arguments"]=self.request["arguments"]+[{"kind":"boolean","name":"force","value":True}]
        self.assertEqual(self.check(request=r)["reason"],"EXACT_ARGUMENTS_MISMATCH")
    def test_changed_selected_argument(self):
        r=dict(self.request);r["arguments"]=[{"kind":"string","name":"target","value":"other"}]
        self.assertEqual(self.check(request=r)["reason"],"EXACT_ARGUMENTS_MISMATCH")
    def test_excess_request_field_rejected_by_actual_schema(self):
        r=dict(self.request);r["fakeAuthorization"]=True
        self.assertEqual(self.check(request=r)["reason"],"TOOLREQUEST_SCHEMA_OR_FINGERPRINT_REJECTED")
    def test_fabricated_positive_assessment_refused(self):
        from dataclasses import replace
        forged=replace(self.assessment,weakest_probability=1.0)
        self.assertEqual(self.check(assessment=forged)["reason"],"ASSESSMENT_RECOMPUTATION_MISMATCH")
    def test_changed_probabilities_require_recalculation(self):
        altered={"action":0.1,"target":0.91}
        self.assertEqual(self.check(decision_probabilities=altered)["reason"],"ASSESSMENT_RECOMPUTATION_MISMATCH")
    def test_low_confidence_decision_refused(self):
        a=f.assess_proposal(self.offer,selected="inspect",parameters=self.params,
                            probabilities={"action":0.21,"target":0.95},
                            declared_offering_digest=self.offer.digest,thresholds=self.thresholds)
        self.assertEqual(self.check(assessment=a)["reason"],"PROPOSAL_NOT_REVIEWABLE")

if __name__=="__main__":
    unittest.main(verbosity=2)
