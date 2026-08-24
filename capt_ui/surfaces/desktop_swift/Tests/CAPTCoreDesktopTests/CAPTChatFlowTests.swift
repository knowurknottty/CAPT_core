import XCTest
@testable import CAPTCoreDesktop

final class CAPTChatFlowTests: XCTestCase {
    private func pending(expiresAt: Date? = Date.distantFuture) -> CAPTPendingApproval {
        CAPTPendingApproval(
            requestID: "approval-1",
            missionID: "mission-1",
            taskID: "task-1",
            driverRunID: "run-1",
            objective: "inspect repo",
            targetRoot: "/repo",
            provider: "openrouter",
            model: "model-a",
            promptAssemblyDigest: "sha256:abc",
            expiresAt: expiresAt
        )
    }

    func testFreshPendingStartsAwaitingApproval() {
        let approval = pending(expiresAt: Date(timeIntervalSince1970: 2_000))
        let flow = CAPTChatFlow(
            pending: approval,
            now: Date(timeIntervalSince1970: 1_000)
        )
        XCTAssertEqual(flow.phase, .awaitingApproval)
        XCTAssertEqual(flow.requestID, "approval-1")
        XCTAssertFalse(flow.canCompose)
    }

    func testExpiredPendingIsRecoverableAndNonActionable() {
        let approval = pending(expiresAt: Date(timeIntervalSince1970: 1_000))
        let flow = CAPTChatFlow(
            pending: approval,
            now: Date(timeIntervalSince1970: 2_000)
        )
        XCTAssertEqual(flow.phase, .recoverableFailure)
        XCTAssertNil(flow.requestID)
        XCTAssertTrue(flow.canCompose)
    }

    func testUnknownExpiryPendingIsRecoverableAndNonActionable() {
        let flow = CAPTChatFlow(
            pending: pending(expiresAt: nil),
            now: Date(timeIntervalSince1970: 2_000)
        )
        XCTAssertEqual(flow.phase, .recoverableFailure)
        XCTAssertNil(flow.requestID)
        XCTAssertTrue(flow.canCompose)
        XCTAssertEqual(flow.failureMessage, "Prompt approval validity unavailable")
    }

    func testProviderFailureKeepsApprovalRetryable() {
        let approval = pending()
        var flow = CAPTChatFlow(pending: approval)
        flow.beginExecution(approval)
        let disposition = flow.executionFailed(
            message: "PROVIDER_CREDENTIAL_UNAVAILABLE",
            pending: approval
        )
        XCTAssertEqual(disposition, .retryable)
        XCTAssertEqual(flow.phase, .recoverableFailure)
        XCTAssertEqual(flow.requestID, "approval-1")
        XCTAssertFalse(flow.canCompose)
    }

    func testExpiredRuntimeFailureDropsLocalActionCursor() {
        let approval = pending()
        var flow = CAPTChatFlow(pending: approval)
        let disposition = flow.executionFailed(
            message: "PROMPT_APPROVAL_EXPIRED: prompt approval expired",
            pending: approval
        )
        XCTAssertEqual(disposition, .expired)
        XCTAssertNil(flow.requestID)
        XCTAssertTrue(flow.canCompose)
    }

    func testExecutionCompletionAllowsContinuationWhileAwaitingVerification() {
        var flow = CAPTChatFlow()
        flow.executionCompleted(taskState: "awaiting_verification")
        XCTAssertEqual(flow.phase, .awaitingVerification)
        XCTAssertTrue(flow.canCompose)
    }
}

extension CAPTChatFlowTests {
    private func proposal() throws -> CAPTPromptProposal {
        try CAPTPromptProposal(dictionary: [
            "proposalId": "pp-1", "revision": 0, "state": "active",
            "status": "ready_for_approval", "originalPrompt": "fix",
            "proposedPrompt": "compiled fix", "originalPromptDigest": "sha256:o",
            "proposedPromptDigest": "sha256:p", "stageChain": ["OMNI", "META"],
            "stageRecords": [], "verificationContract": ["acceptanceCriteria": []],
            "unresolvedQuestions": [], "targetRoot": "/repo", "rationale": "route"
        ])
    }

    func testProposalStartsInReviewAndBlocksComposition() throws {
        let flow = CAPTChatFlow(proposal: try proposal())
        XCTAssertEqual(flow.phase, .reviewingProposal)
        XCTAssertEqual(flow.proposalID, "pp-1")
        XCTAssertFalse(flow.canCompose)
    }

    func testCompilationTransitionsToProposalReview() throws {
        var flow = CAPTChatFlow()
        flow.beginCompilation()
        XCTAssertEqual(flow.phase, .compilingProposal)
        flow.proposalPrepared(try proposal())
        XCTAssertEqual(flow.phase, .reviewingProposal)
    }
}
