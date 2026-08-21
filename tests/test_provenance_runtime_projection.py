"""CAPT-UPG-017: authoritative projection must expose current governed aggregate kinds."""
from __future__ import annotations

from desktop.desktop_runtime_client import project_authoritative_state


class _Client:
    def __init__(self):
        self.states = {
            "mission-m-1": {"missionId": "m-1", "state": "active"},
            "task-t-1": {"taskId": "t-1", "missionId": "m-1", "state": "running"},
            "human_approval-ap-1": {"requestId": "ap-1", "missionId": "m-1", "taskId": "t-1", "state": "approved"},
            "driverrun-dr-1": {"driverRunId": "dr-1", "missionId": "m-1", "taskId": "t-1", "state": "completed"},
            "claim-cl-1": {"claimId": "cl-1", "missionId": "m-1", "taskId": "t-1", "promotionState": "accepted"},
            "capability-g-1": {"grantId": "g-1", "capabilityId": "cap.fs.read", "grantState": "leased", "lease": {"leaseId": "l-1", "missionId": "m-1", "taskId": "t-1", "state": "active"}},
            "artifact_promotion-p-1": {"promotionId": "p-1", "claimId": "cl-1", "verificationId": "ver-1", "evidenceId": "ev-1", "state": "adopted"},
            "cohort-coh-1": {"cohortId": "coh-1", "missionId": "m-1", "taskId": "t-1", "epoch": 1, "rounds": 1, "evidenceIds": ["ev-cohort-1"]},
            "replay_fork-f-1": {"forkId": "f-1", "sourceSequence": 10, "sourceStateDigest": "sha256:" + "1" * 64, "sourceChainDigest": "sha256:" + "2" * 64, "newMissionId": "m-1", "historicalAuthorityReactivated": False, "state": "created"},
        }
        self.kinds = {
            "mission-m-1": "mission",
            "task-t-1": "task",
            "human_approval-ap-1": "human_approval",
            "driverrun-dr-1": "driverrun",
            "claim-cl-1": "claim",
            "capability-g-1": "capability",
            "artifact_promotion-p-1": "artifact_promotion",
            "cohort-coh-1": "cohort",
            "replay_fork-f-1": "replay_fork",
        }

    def list_aggregates(self):
        return [
            {"streamId": stream_id, "kind": self.kinds[stream_id], "version": 1}
            for stream_id in sorted(self.states)
        ]

    def get_state(self, stream_id):
        return self.states.get(stream_id)

    def verification(self, claim_id=None):
        return {
            "verificationId": "ver-1",
            "claimId": claim_id,
            "status": {"kind": "verified", "supportingEvidenceIds": ["ev-1"]},
            "committed": True,
            "advisory": False,
        }

    def event_timeline(self):
        return []

    def identity(self):
        return {"headSequence": 42, "integrity": "ok"}


def test_authoritative_projection_exposes_governed_aggregate_families_for_provenance():
    state = project_authoritative_state(_Client())

    assert [x["grantId"] for x in state["capabilities"]] == ["g-1"]
    assert [x["promotionId"] for x in state["artifactPromotions"]] == ["p-1"]
    assert [x["cohortId"] for x in state["cohorts"]] == ["coh-1"]
    assert [x["forkId"] for x in state["replayForks"]] == ["f-1"]
    assert state["verificationsByClaim"]["cl-1"]["status"]["supportingEvidenceIds"] == ["ev-1"]
