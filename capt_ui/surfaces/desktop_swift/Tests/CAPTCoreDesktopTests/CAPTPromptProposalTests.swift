import XCTest
@testable import CAPTCoreDesktop

final class CAPTPromptProposalTests: XCTestCase {
    private func payload() -> [String: Any] {
        [
            "proposalId": "pp-1", "revision": 2, "state": "active",
            "status": "ready_for_approval",
            "originalPrompt": "fix provider", "proposedPrompt": "compiled provider fix",
            "originalPromptDigest": "sha256:original",
            "proposedPromptDigest": "sha256:compiled",
            "stageChain": ["OMNI", "META", "FORGE", "SIGMA"],
            "stageRecords": [[
                "stage": "FORGE", "executionEnabled": true,
                "provider": "mtplx", "model": "qwen3.8-27b-mtplx",
                "endpointClass": "local", "rationale": "bounded repository scan"
            ]],
            "verificationContract": ["acceptanceCriteria": ["tests pass"]],
            "unresolvedQuestions": ["none"], "targetRoot": "/repo",
            "provider": "mtplx", "model": "qwen3.8-27b-mtplx",
            "rationale": "software route"
        ]
    }

    func testProposalDecodesStrictIdentityAndStageChain() throws {
        let proposal = try CAPTPromptProposal(dictionary: payload())
        XCTAssertEqual(proposal.proposalID, "pp-1")
        XCTAssertEqual(proposal.revision, 2)
        XCTAssertEqual(proposal.stageChain, ["OMNI", "META", "FORGE", "SIGMA"])
        XCTAssertEqual(proposal.stageRecords.first?.endpointClass, "local")
        XCTAssertEqual(proposal.verificationCriteria, ["tests pass"])
        XCTAssertEqual(proposal.selectedPrompt(.upgrade), "compiled provider fix")
        XCTAssertTrue(proposal.hasMaterialUpgrade)
    }

    func testProposalDecodeRejectsMissingIdentity() {
        var value = payload()
        value.removeValue(forKey: "proposalId")
        XCTAssertThrowsError(try CAPTPromptProposal(dictionary: value))
    }

    func testEditedSelectionTrimsOnlyOperatorEdit() throws {
        let proposal = try CAPTPromptProposal(dictionary: payload())
        XCTAssertEqual(proposal.selectedPrompt(.edited, edited: "  custom prompt\n"), "custom prompt")
    }
}


extension CAPTPromptProposalTests {
    func testLegacyModelGeneratedClarificationRemainsApprovalSelectable() throws {
        var value = payload()
        value["status"] = "clarification_required"
        let proposal = try CAPTPromptProposal(dictionary: value)
        XCTAssertTrue(proposal.isApprovalSelectable)
    }

    func testDeterministicClarificationWithoutExecutedStageRemainsBlocked() throws {
        var value = payload()
        value["status"] = "clarification_required"
        value["stageRecords"] = [[
            "stage": "OMNI", "executionEnabled": false,
            "provider": "openrouter", "model": "z-ai/glm-5.3-flash",
            "endpointClass": "remote", "rationale": "clarification required"
        ]]
        let proposal = try CAPTPromptProposal(dictionary: value)
        XCTAssertFalse(proposal.isApprovalSelectable)
    }
}
