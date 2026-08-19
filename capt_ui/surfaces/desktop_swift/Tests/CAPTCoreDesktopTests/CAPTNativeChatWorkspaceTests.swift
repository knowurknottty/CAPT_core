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

    func testSwitchingAwayAndBackPreservesInFlightApprovalRequest() {
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
        XCTAssertEqual(workspace.activeFlow.phase, .requestingApproval)

        _ = workspace.newChat(
            id: newID, provider: "openrouter", model: "model-a", targetRoot: "/repo"
        )
        XCTAssertTrue(workspace.activate(oldID))
        XCTAssertEqual(workspace.activeFlow.phase, .requestingApproval)
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
        XCTAssertEqual(workspace.flow(for: newID).phase, .requestingApproval)
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
        XCTAssertEqual(workspace.flow(for: oldID).phase, .requestingApproval)
        XCTAssertEqual(workspace.sessions.count, 1)
    }
}
