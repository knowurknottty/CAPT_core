import XCTest
@testable import CAPTCoreDesktop

final class CAPTNativeChatWorkspaceTests: XCTestCase {
    private let oldID = UUID(uuidString: "00000000-0000-0000-0000-000000000101")!
    private let newID = UUID(uuidString: "00000000-0000-0000-0000-000000000102")!

    private func pending(
        requestID: String = "approval-1",
        expiresAt: Date? = nil
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
}
