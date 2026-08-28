import XCTest
@testable import CAPTCoreDesktop

final class CAPTNativeChatWorkspaceTests: XCTestCase {
    private let oldID = UUID(uuidString: "00000000-0000-0000-0000-000000000101")!
    private let newID = UUID(uuidString: "00000000-0000-0000-0000-000000000102")!

    private func pending(
        requestID: String = "approval-1",
        expiresAt: Date? = Date.distantFuture
    ) -> CAPTPendingApproval {
        CAPTPendingApproval(
            requestID: requestID,
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

    func testNewChatNeverInheritsPreviousPendingApproval() {
        let old = CAPTNativeSession(
            id: oldID, missionID: "mission-1", title: "Old",
            messages: [], provider: "openrouter", model: "model-a",
            targetRoot: "/repo", pendingApproval: pending()
        )
        var workspace = CAPTNativeChatWorkspace(
            sessions: [old], activeSessionID: oldID
        )

        let created = workspace.newChat(
            id: newID,
            provider: "openrouter",
            model: "model-a",
            targetRoot: "/repo"
        )

        XCTAssertEqual(created, newID)
        XCTAssertEqual(workspace.activeSessionID, newID)
        XCTAssertNil(workspace.activePendingApproval)
        XCTAssertEqual(workspace.session(oldID)?.pendingApproval?.requestID, "approval-1")
    }

    func testSwitchingAwayAndBackPreservesInFlightPromptCompilation() {
        var workspace = CAPTNativeChatWorkspace()
        _ = workspace.newChat(
            id: oldID, provider: "openrouter", model: "model-a", targetRoot: "/repo"
        )
        XCTAssertEqual(
            workspace.beginPrompt(
                "first prompt", provider: "openrouter", model: "model-a", targetRoot: "/repo"
            ),
            oldID
        )
        XCTAssertEqual(workspace.activeFlow.phase, .compilingProposal)

        _ = workspace.newChat(
            id: newID, provider: "openrouter", model: "model-a", targetRoot: "/repo"
        )
        XCTAssertTrue(workspace.activate(oldID))
        XCTAssertEqual(workspace.activeFlow.phase, .compilingProposal)
        XCTAssertFalse(workspace.activeFlow.canCompose)
    }

    func testLateApprovalResultIsAppliedToOriginatingSessionAfterSwitch() {
        var workspace = CAPTNativeChatWorkspace()
        _ = workspace.newChat(
            id: oldID, provider: "openrouter", model: "model-a", targetRoot: "/repo"
        )
        let origin = workspace.beginPrompt(
            "first prompt", provider: "openrouter", model: "model-a", targetRoot: "/repo"
        )!
        _ = workspace.newChat(
            id: newID, provider: "openrouter", model: "model-a", targetRoot: "/repo"
        )

        workspace.receiveApproval(pending(), for: origin)

        XCTAssertEqual(workspace.activeSessionID, newID)
        XCTAssertNil(workspace.activePendingApproval)
        XCTAssertEqual(workspace.session(oldID)?.pendingApproval?.requestID, "approval-1")
        XCTAssertEqual(workspace.flow(for: oldID).phase, .awaitingApproval)
    }

    func testLateConfigurationUpdateTargetsOriginatingSessionAfterSwitch() {
        var workspace = CAPTNativeChatWorkspace()
        _ = workspace.newChat(
            id: oldID, provider: "ollama", model: "old-model", targetRoot: "/old"
        )
        _ = workspace.newChat(
            id: newID, provider: "openrouter", model: "new-model", targetRoot: "/new"
        )

        workspace.updateConfiguration(
            for: oldID, provider: "mlx", model: "late-model", targetRoot: "/old"
        )

        XCTAssertEqual(workspace.activeSessionID, newID)
        XCTAssertEqual(workspace.session(oldID)?.provider, "mlx")
        XCTAssertEqual(workspace.session(oldID)?.model, "late-model")
        XCTAssertEqual(workspace.session(newID)?.provider, "openrouter")
        XCTAssertEqual(workspace.session(newID)?.model, "new-model")
    }

    func testReconcileActiveApprovalValidityExpiresWhileChatStaysOpen() {
        let approval = pending(expiresAt: Date(timeIntervalSince1970: 1_000))
        let old = CAPTNativeSession(
            id: oldID, missionID: "mission-1", title: "Old",
            messages: [], provider: "openrouter", model: "model-a",
            targetRoot: "/repo", pendingApproval: approval
        )
        var workspace = CAPTNativeChatWorkspace(
            sessions: [old], activeSessionID: oldID,
            now: Date(timeIntervalSince1970: 500)
        )

        workspace.reconcileActiveApprovalValidity(now: Date(timeIntervalSince1970: 2_000))

        XCTAssertNil(workspace.activePendingApproval)
        XCTAssertEqual(workspace.activeSession?.missionID, "mission-1")
        XCTAssertEqual(workspace.activeFlow.phase, .recoverableFailure)
        XCTAssertEqual(workspace.activeSession?.messages.last?.authorityState, "approval_expired")
    }

    func testConfigurationMutationInvalidatesBoundApprovalCursor() {
        let old = CAPTNativeSession(
            id: oldID, missionID: "mission-1", title: "Old",
            messages: [], provider: "openrouter", model: "model-a",
            targetRoot: "/repo", pendingApproval: pending()
        )
        var workspace = CAPTNativeChatWorkspace(
            sessions: [old], activeSessionID: oldID
        )

        workspace.updateConfiguration(
            for: oldID, provider: "mtplx", model: "qwen3.8-27b-mtplx", targetRoot: "/repo"
        )

        XCTAssertNil(workspace.activePendingApproval)
        XCTAssertEqual(workspace.activeSession?.provider, "mtplx")
        XCTAssertEqual(workspace.activeSession?.model, "qwen3.8-27b-mtplx")
        XCTAssertEqual(workspace.activeFlow.phase, .recoverableFailure)
        XCTAssertEqual(workspace.activeSession?.messages.last?.authorityState, "approval_superseded")
    }

    func testLateApprovalForSupersededConfigurationIsNotMadeActionable() {
        var workspace = CAPTNativeChatWorkspace()
        _ = workspace.newChat(
            id: oldID, provider: "openrouter", model: "model-a", targetRoot: "/repo"
        )
        let origin = workspace.beginPrompt(
            "first prompt", provider: "openrouter", model: "model-a", targetRoot: "/repo"
        )!

        workspace.updateConfiguration(
            for: oldID, provider: "mtplx", model: "qwen3.8-27b-mtplx", targetRoot: "/repo"
        )
        workspace.receiveApproval(pending(), for: origin)

        XCTAssertNil(workspace.session(oldID)?.pendingApproval)
        XCTAssertTrue(workspace.flow(for: oldID).canCompose)
        XCTAssertEqual(workspace.session(oldID)?.messages.last?.authorityState, "approval_superseded")
    }

    func testActivatingExpiredApprovalClearsLocalCursorButKeepsMission() {
        let approval = pending(expiresAt: Date(timeIntervalSince1970: 1_000))
        let old = CAPTNativeSession(
            id: oldID, missionID: "mission-1", title: "Old",
            messages: [], provider: "openrouter", model: "model-a",
            targetRoot: "/repo", pendingApproval: approval
        )
        var workspace = CAPTNativeChatWorkspace(
            sessions: [old],
            activeSessionID: nil,
            now: Date(timeIntervalSince1970: 500)
        )

        XCTAssertTrue(workspace.activate(oldID, now: Date(timeIntervalSince1970: 2_000)))
        XCTAssertNil(workspace.activePendingApproval)
        XCTAssertEqual(workspace.activeSession?.missionID, "mission-1")
        XCTAssertEqual(workspace.activeFlow.phase, .recoverableFailure)
        XCTAssertEqual(workspace.activeSession?.messages.last?.authorityState, "approval_expired")
    }

    func testActivatingLegacyApprovalWithoutExpiryClearsLocalCursor() {
        let old = CAPTNativeSession(
            id: oldID, missionID: "mission-1", title: "Legacy",
            messages: [], provider: "openrouter", model: "model-a",
            targetRoot: "/repo", pendingApproval: pending(expiresAt: nil)
        )
        var workspace = CAPTNativeChatWorkspace(
            sessions: [old], activeSessionID: nil
        )

        XCTAssertTrue(workspace.activate(oldID))
        XCTAssertNil(workspace.activePendingApproval)
        XCTAssertEqual(workspace.activeSession?.missionID, "mission-1")
        XCTAssertEqual(workspace.activeFlow.phase, .recoverableFailure)
        XCTAssertEqual(workspace.activeSession?.messages.last?.authorityState, "approval_stale")
    }

    func testRetryableExecutionFailureKeepsApprovalForRetry() {
        let old = CAPTNativeSession(
            id: oldID, missionID: "mission-1", title: "Old",
            messages: [], provider: "openrouter", model: "model-a",
            targetRoot: "/repo", pendingApproval: pending()
        )
        var workspace = CAPTNativeChatWorkspace(
            sessions: [old], activeSessionID: oldID
        )

        XCTAssertNotNil(workspace.beginExecution(for: oldID))
        let disposition = workspace.failExecution(
            message: "PROVIDER_CREDENTIAL_UNAVAILABLE", for: oldID
        )

        XCTAssertEqual(disposition, .retryable)
        XCTAssertEqual(workspace.session(oldID)?.pendingApproval?.requestID, "approval-1")
        XCTAssertEqual(workspace.flow(for: oldID).phase, .recoverableFailure)
    }

    func testTerminalApprovalFailureDropsLocalActionCursor() {
        let old = CAPTNativeSession(
            id: oldID, missionID: "mission-1", title: "Old",
            messages: [], provider: "openrouter", model: "model-a",
            targetRoot: "/repo", pendingApproval: pending()
        )
        var workspace = CAPTNativeChatWorkspace(
            sessions: [old], activeSessionID: oldID
        )

        let disposition = workspace.failExecution(
            message: "PROMPT_APPROVAL_EXPIRED: prompt approval expired", for: oldID
        )

        XCTAssertEqual(disposition, .expired)
        XCTAssertNil(workspace.session(oldID)?.pendingApproval)
        XCTAssertTrue(workspace.flow(for: oldID).canCompose)
        XCTAssertEqual(workspace.session(oldID)?.messages.last?.authorityState, "approval_expired")
    }

    func testAsyncRestoreMergesWithoutReplacingLiveChat() {
        var workspace = CAPTNativeChatWorkspace()
        _ = workspace.newChat(
            id: newID, provider: "openrouter", model: "live-model", targetRoot: "/live"
        )
        _ = workspace.beginPrompt(
            "live prompt", provider: "openrouter", model: "live-model", targetRoot: "/live"
        )
        let restored = CAPTNativeSession(
            id: oldID,
            missionID: "mission-restored",
            title: "Restored",
            createdAt: Date(timeIntervalSince1970: 100),
            updatedAt: Date(timeIntervalSince1970: 200),
            messages: [],
            provider: "ollama",
            model: "restored-model",
            targetRoot: "/restored"
        )

        workspace.mergeRestoredSessions([restored])

        XCTAssertEqual(workspace.activeSessionID, newID)
        XCTAssertEqual(workspace.session(newID)?.messages.last?.text, "live prompt")
        XCTAssertEqual(workspace.flow(for: newID).phase, .compilingProposal)
        XCTAssertEqual(workspace.session(oldID)?.missionID, "mission-restored")
        XCTAssertEqual(workspace.sessions.count, 2)
    }

    func testAsyncRestoreNeverOverwritesSameIDLiveMutation() {
        let seed = CAPTNativeSession(
            id: oldID,
            title: "Cached",
            createdAt: Date(timeIntervalSince1970: 100),
            updatedAt: Date(timeIntervalSince1970: 200),
            messages: [],
            provider: "ollama",
            model: "cached-model",
            targetRoot: "/cached"
        )
        var workspace = CAPTNativeChatWorkspace(
            sessions: [seed], activeSessionID: oldID
        )
        _ = workspace.beginPrompt(
            "live mutation", provider: "openrouter", model: "live-model", targetRoot: "/live"
        )
        let restoredDuplicate = CAPTNativeSession(
            id: oldID,
            title: "Older disk copy",
            createdAt: Date(timeIntervalSince1970: 100),
            updatedAt: Date(timeIntervalSince1970: 150),
            messages: [],
            provider: "ollama",
            model: "older-model",
            targetRoot: "/older"
        )

        workspace.mergeRestoredSessions([restoredDuplicate])

        XCTAssertEqual(workspace.session(oldID)?.title, "Cached")
        XCTAssertEqual(workspace.session(oldID)?.model, "live-model")
        XCTAssertEqual(workspace.session(oldID)?.messages.last?.text, "live mutation")
        XCTAssertEqual(workspace.flow(for: oldID).phase, .compilingProposal)
        XCTAssertEqual(workspace.sessions.count, 1)
    }
}

extension CAPTNativeChatWorkspaceTests {
    private func proposal(
        id: String = "pp-1", provider: String = "openrouter", model: String = "model-a"
    ) throws -> CAPTPromptProposal {
        try CAPTPromptProposal(dictionary: [
            "proposalId": id, "revision": 0, "state": "active",
            "status": "ready_for_approval", "originalPrompt": "first prompt",
            "proposedPrompt": "compiled first prompt", "originalPromptDigest": "sha256:o",
            "proposedPromptDigest": "sha256:p", "stageChain": ["OMNI", "META"],
            "stageRecords": [], "verificationContract": ["acceptanceCriteria": []],
            "unresolvedQuestions": [], "targetRoot": "/repo",
            "provider": provider, "model": model, "rationale": "route"
        ])
    }

    func testBeginPromptEntersCompilingProposal() {
        var workspace = CAPTNativeChatWorkspace()
        _ = workspace.newChat(
            id: oldID, provider: "openrouter", model: "model-a", targetRoot: "/repo"
        )
        XCTAssertEqual(workspace.beginPrompt(
            "first prompt", provider: "openrouter", model: "model-a", targetRoot: "/repo"
        ), oldID)
        XCTAssertEqual(workspace.activeFlow.phase, .compilingProposal)
        XCTAssertNil(workspace.activePromptProposal)
    }

    func testLateProposalStaysOnOriginatingSessionAfterSwitch() throws {
        var workspace = CAPTNativeChatWorkspace()
        _ = workspace.newChat(
            id: oldID, provider: "openrouter", model: "model-a", targetRoot: "/repo"
        )
        let origin = workspace.beginPrompt(
            "first prompt", provider: "openrouter", model: "model-a", targetRoot: "/repo"
        )!
        _ = workspace.newChat(
            id: newID, provider: "openrouter", model: "model-a", targetRoot: "/repo"
        )
        workspace.receiveProposal(try proposal(), for: origin)
        XCTAssertEqual(workspace.activeSessionID, newID)
        XCTAssertNil(workspace.activePromptProposal)
        XCTAssertEqual(workspace.session(oldID)?.promptProposal?.proposalID, "pp-1")
        XCTAssertEqual(workspace.flow(for: oldID).phase, .reviewingProposal)
    }

    func testConfigurationMutationInvalidatesProposal() throws {
        let session = CAPTNativeSession(
            id: oldID, title: "Old", provider: "openrouter", model: "model-a",
            targetRoot: "/repo", promptProposal: try proposal()
        )
        var workspace = CAPTNativeChatWorkspace(sessions: [session], activeSessionID: oldID)
        workspace.updateConfiguration(
            for: oldID, provider: "mtplx", model: "qwen", targetRoot: "/repo"
        )
        XCTAssertNil(workspace.activePromptProposal)
        XCTAssertEqual(workspace.activeFlow.phase, .recoverableFailure)
        XCTAssertEqual(workspace.activeSession?.messages.last?.authorityState, "proposal_superseded")
    }

    func testBeginProposalApprovalReturnsBoundProposal() throws {
        let session = CAPTNativeSession(
            id: oldID, title: "Old", provider: "openrouter", model: "model-a",
            targetRoot: "/repo", promptProposal: try proposal()
        )
        var workspace = CAPTNativeChatWorkspace(sessions: [session], activeSessionID: oldID)
        let bound = workspace.beginProposalApproval(for: oldID)
        XCTAssertEqual(bound?.proposalID, "pp-1")
        XCTAssertEqual(workspace.activeFlow.phase, .requestingApproval)
        XCTAssertFalse(workspace.activeFlow.canCompose)
    }

    func testChatsRetainIndependentExecutionModelsWhenSwitching() {
        var workspace = CAPTNativeChatWorkspace()
        _ = workspace.newChat(
            id: oldID, provider: "openrouter", model: "z-ai/glm-5.3-flash", targetRoot: "/repo-a"
        )
        _ = workspace.newChat(
            id: newID, provider: "openrouter", model: "tencent/hy3", targetRoot: "/repo-b"
        )

        XCTAssertTrue(workspace.activate(oldID))
        XCTAssertEqual(workspace.activeSession?.model, "z-ai/glm-5.3-flash")
        workspace.updateConfiguration(
            for: oldID, provider: "openrouter", model: "xiaomi/mimo-v2.5", targetRoot: "/repo-a"
        )

        XCTAssertTrue(workspace.activate(newID))
        XCTAssertEqual(workspace.activeSession?.model, "tencent/hy3")
        XCTAssertEqual(workspace.activeSession?.targetRoot, "/repo-b")
        XCTAssertTrue(workspace.activate(oldID))
        XCTAssertEqual(workspace.activeSession?.model, "xiaomi/mimo-v2.5")
        XCTAssertEqual(workspace.activeSession?.targetRoot, "/repo-a")
    }


    func testAuthoritativeSuspensionRetiresConsumedApprovalAndStopsExecutingFlow() {
        let session = CAPTNativeSession(
            id: oldID, missionID: "mission-1", title: "Old",
            messages: [], provider: "openrouter", model: "z-ai/glm-5.3-flash",
            targetRoot: "/repo", pendingApproval: pending()
        )
        var workspace = CAPTNativeChatWorkspace(sessions: [session], activeSessionID: oldID)
        XCTAssertNotNil(workspace.beginExecution(for: oldID))
        XCTAssertEqual(workspace.activeFlow.phase, .executing)

        XCTAssertTrue(workspace.reconcileAuthoritativeExecutionState("suspended", for: oldID))

        XCTAssertNil(workspace.activePendingApproval)
        XCTAssertNil(workspace.activePromptProposal)
        XCTAssertEqual(workspace.activeFlow.phase, .recoverableFailure)
        XCTAssertEqual(workspace.activeSession?.messages.last?.authorityState, "reconciliation_required")
        XCTAssertTrue(workspace.activeFlow.canCompose)
    }

    func testAuthoritativeRunningStateDoesNotMutateLocalExecutionCursor() {
        let session = CAPTNativeSession(
            id: oldID, title: "Old", messages: [], provider: "openrouter",
            model: "z-ai/glm-5.3-flash", targetRoot: "/repo", pendingApproval: pending()
        )
        var workspace = CAPTNativeChatWorkspace(sessions: [session], activeSessionID: oldID)
        XCTAssertNotNil(workspace.beginExecution(for: oldID))

        XCTAssertFalse(workspace.reconcileAuthoritativeExecutionState("running", for: oldID))
        XCTAssertNotNil(workspace.activePendingApproval)
        XCTAssertEqual(workspace.activeFlow.phase, .executing)
    }

}
