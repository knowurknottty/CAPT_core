import Foundation
import XCTest
@testable import CAPTCoreDesktop

final class CAPTRuntimeProfileIsolationTests: XCTestCase {
    func testLabsProfileWritesMissionOnlyToLabsLedger() throws {
        guard ProcessInfo.processInfo.environment["CAPT_PROFILE_ISOLATION_TEST"] == "1" else {
            throw XCTSkip("Set CAPT_PROFILE_ISOLATION_TEST=1 for real isolated-runtime proof")
        }
        let realHome = FileManager.default.homeDirectoryForCurrentUser
        let labsVenv = realHome.appendingPathComponent(".capt-inversion-labs/runtime-venv", isDirectory: true)
        guard FileManager.default.fileExists(atPath: labsVenv.path) else {
            throw XCTSkip("Labs runtime venv is not installed")
        }

        let nonce = UUID().uuidString.replacingOccurrences(of: "-", with: "")
        let fakeHome = URL(fileURLWithPath: "/tmp", isDirectory: true)
            .appendingPathComponent("capt-pi-" + String(nonce.prefix(8)), isDirectory: true)
        let standard = CAPTRuntimeProfile.resolve(
            home: fakeHome.path, environment: [:], bundleIdentifier: CAPTRuntimeProfile.standardBundleIdentifier
        )
        let labs = CAPTRuntimeProfile.resolve(
            home: fakeHome.path, environment: [:], bundleIdentifier: CAPTRuntimeProfile.labsBundleIdentifier
        )
        try FileManager.default.createDirectory(
            at: URL(fileURLWithPath: labs.stateDirectory), withIntermediateDirectories: true
        )
        try FileManager.default.createSymbolicLink(
            at: URL(fileURLWithPath: labs.stateDirectory).appendingPathComponent("runtime-venv"),
            withDestinationURL: labsVenv
        )

        let executable = labs.runtimeExecutableCandidates[0]
        defer {
            let stop = Process()
            stop.executableURL = URL(fileURLWithPath: executable)
            stop.arguments = ["stop", "--state-dir", labs.stateDirectory]
            try? stop.run()
            stop.waitUntilExit()
            try? FileManager.default.removeItem(at: fakeHome)
        }

        try CAPTRuntimeBootstrapper(profile: labs).start()
        let client = CAPTRuntimeClient(profile: labs)
        defer { client.disconnect() }
        _ = try client.connect()

        let missionID = "m-profile-" + String(nonce.prefix(8)).lowercased()
        let payload: [String: Any] = [
            "schemaVersion": "1.0.0", "missionId": missionID,
            "objective": "CAPT Labs state-root isolation proof. READ-ONLY.",
            "rawRequest": "state-root isolation proof", "normalizedRequest": "state-root isolation proof",
            "constraints": [], "successCriteria": [], "terminationCriteria": [],
            "unresolvedAmbiguities": [], "requiresApproval": false,
            "requestedCapability": "cap.fs.read", "operation": "RepositoryRead",
            "scope": ["kind": "filesystem", "rootPath": "/tmp", "recursive": false],
            "riskClassification": "low", "policyReason": "isolated state-root verification"
        ]
        let receipt = try client.command(
            op: "create_mission", payload: payload,
            idempotencyKey: "profile-isolation-" + missionID
        )
        XCTAssertEqual(receipt["status"] as? String, "accepted")
        let result = try XCTUnwrap(receipt["result"] as? [String: Any])
        let taskID = try XCTUnwrap(result["taskId"] as? String)
        let mission = try client.query(
            op: "get_state", payload: ["streamId": "mission-" + missionID]
        )["result"] as? [String: Any]
        let task = try client.query(
            op: "get_state", payload: ["streamId": "task-" + taskID]
        )["result"] as? [String: Any]

        XCTAssertEqual(mission?["missionId"] as? String, missionID)
        XCTAssertEqual(task?["taskId"] as? String, taskID)
        XCTAssertTrue(
            FileManager.default.fileExists(
                atPath: URL(fileURLWithPath: labs.stateDirectory).appendingPathComponent("runtime.db").path
            )
        )
        XCTAssertFalse(
            FileManager.default.fileExists(
                atPath: URL(fileURLWithPath: standard.stateDirectory).appendingPathComponent("runtime.db").path
            )
        )
    }
}
