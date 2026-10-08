import Foundation
import XCTest
@testable import CAPTCoreDesktop

private final class CouncilRuntimeStub: CAPTRuntimeCommanding {
    var calls: [(String, [String: Any], String?)] = []
    var approvalState: [String: String] = [:]
    var requestedIDs: [String: String] = [:]

    func connect() throws -> [String: Any] { [:] }
    func disconnect() {}
    func query(op: String, payload: [String: Any]) throws -> [String: Any] {
        calls.append((op, payload, nil))
        let stream = payload["streamId"] as? String ?? ""
        let id = String(stream.dropFirst("human_approval-".count))
        return ["ok": true, "result": [
            "requestId": id, "state": approvalState[id] ?? "requested"
        ]]
    }
    func command(op: String, payload: [String: Any], idempotencyKey: String?) throws -> [String: Any] {
        calls.append((op, payload, idempotencyKey))
        switch op {
        case "request_model_prompt_approval":
            let spec = payload["cohortSpec"] as! [String: Any]
            let cohortID = spec["cohortId"] as! String
            let requestID = "approval-" + cohortID
            requestedIDs[cohortID] = requestID
            approvalState[requestID] = "requested"
            return ["status": "accepted", "result": [
                "requestId": requestID, "taskId": payload["taskId"]!,
                "driverRunId": payload["driverRunId"]!,
                "expiresAt": "2099-01-01T00:00:00Z"
            ]]
        case "submit_approval_decision":
            let id = payload["requestId"] as! String
            approvalState[id] = payload["decision"] as? String == "approve" ? "approved" : "denied"
            return ["status": "accepted", "result": ["requestId": id]]
        case "run_approved_council_inspection":
            return ["status": "accepted", "result": [
                "cohortCount": 2, "providerCallInvariant": "one_call_per_cohort"
            ]]
        default:
            XCTFail("Unexpected command " + op)
            return ["status": "rejected"]
        }
    }
}

final class CAPTCouncilCoordinatorTests: XCTestCase {
    private func review() throws -> CAPTCouncilReview {
        try CAPTCouncilReview(
            id: "council-native-test", missionID: "m-shared-audit",
            objective: "Audit CAPT Swift source and produce cited findings",
            targetRoot: "/repo", maxConcurrentCohorts: 2, cohorts: [
                CAPTCouncilCohort(
                    id: "deepseek", provider: "openrouter",
                    model: "deepseek/deepseek-v4.1-flash", vessels: 22
                ),
                CAPTCouncilCohort(
                    id: "mimo", provider: "openrouter",
                    model: "xiaomi/mimo-v2.6-flash", vessels: 22
                ),
            ]
        )
    }

    func testCouncilRequiresOneMissionAndDistinctTypedCohorts() throws {
        let review = try review()
        XCTAssertEqual(review.cohorts.count, 2)
        XCTAssertFalse(review.allApproved)
        XCTAssertEqual(review.maxConcurrentCohorts, 2)
        XCTAssertEqual(review.cohorts.map(\.vessels), [22, 22])
        let payload = review.approvalPayload(at: 0)
        XCTAssertEqual(payload["missionId"] as? String, "m-shared-audit")
        let authority = payload["authorityProfile"] as! [String: Any]
        XCTAssertEqual(authority["fileMutationAllowed"] as? Bool, false)
        XCTAssertEqual(authority["shellAccessAllowed"] as? Bool, false)
        let spec = payload["cohortSpec"] as! [String: Any]
        XCTAssertEqual(spec["vesselsPerCohort"] as? Int, 22)
        XCTAssertThrowsError(try CAPTCouncilReview(
            id: "invalid", missionID: "m", objective: "audit", targetRoot: "/repo",
            maxConcurrentCohorts: 2, cohorts: [
                CAPTCouncilCohort(id: "same", provider: "openrouter", model: "m1", vessels: 22),
                CAPTCouncilCohort(id: "same", provider: "openrouter", model: "m2", vessels: 22),
            ]
        ))
    }

    func testCouncilRequiresTwoExplicitApprovalsBeforeSingleGovernedRun() throws {
        let stub = CouncilRuntimeStub()
        let coordinator = CAPTCouncilCoordinator(client: stub)
        var review = try review()
        XCTAssertThrowsError(try coordinator.run(review))
        XCTAssertTrue(stub.calls.isEmpty)
        for index in review.cohorts.indices {
            review.cohorts[index] = try coordinator.requestApproval(review, at: index)
        }
        XCTAssertEqual(
            stub.calls.map(\.0),
            ["request_model_prompt_approval", "request_model_prompt_approval"]
        )
        XCTAssertThrowsError(try coordinator.run(review))
        XCTAssertEqual(stub.calls.filter { $0.0 == "run_approved_council_inspection" }.count, 0)
        for index in review.cohorts.indices {
            review.cohorts[index] = try coordinator.decide(review.cohorts[index], approve: true)
        }
        XCTAssertTrue(review.allApproved)
        let receipt = try coordinator.run(review)
        XCTAssertTrue(receipt.contains("one_call_per_cohort"))
        let dispatch = try XCTUnwrap(stub.calls.last)
        XCTAssertEqual(dispatch.0, "run_approved_council_inspection")
        let executions = try XCTUnwrap(dispatch.1["executions"] as? [[String: Any]])
        XCTAssertEqual(executions.count, 2)
        XCTAssertEqual(Set(executions.compactMap { $0["missionId"] as? String }), ["m-shared-audit"])
        XCTAssertEqual(executions.map { $0["approvalRequestId"] as? String },
                       ["approval-deepseek", "approval-mimo"])
        XCTAssertEqual(dispatch.1["maxConcurrentCohorts"] as? Int, 2)
        XCTAssertEqual(dispatch.2, "native-council:council-native-test:run")
    }

    func testCouncilRoundTripsWithinLegacyNativeSession() throws {
        var session = CAPTNativeSession(
            title: "Audit", provider: "openrouter", model: "a", targetRoot: "/repo"
        )
        session.councilReview = try review()
        let data = try JSONEncoder().encode(session)
        let restored = try JSONDecoder().decode(CAPTNativeSession.self, from: data)
        XCTAssertEqual(restored.councilReview, session.councilReview)
        session.councilReview = nil
        let legacy = try JSONEncoder().encode(session)
        XCTAssertNil(try JSONDecoder().decode(CAPTNativeSession.self, from: legacy).councilReview)
    }
}

extension CAPTCouncilCoordinatorTests {
    func testConsumedCouncilCanReattachOnlyToExactOriginalLineage() throws {
        let stub = CouncilRuntimeStub()
        let coordinator = CAPTCouncilCoordinator(client: stub)
        var review = try review()
        for index in review.cohorts.indices {
            review.cohorts[index] = try coordinator.requestApproval(review, at: index)
            review.cohorts[index] = try coordinator.decide(
                review.cohorts[index], approve: true
            )
        }
        XCTAssertTrue(review.canRunOrReattach)
        let exact = "native-council:" + review.id + ":run:cohort:"
        // A consumed cohort may only resume its original council idempotency key.
        review.cohorts[0].state = "consumed"
        review.cohorts[0].consumedBy = exact + review.cohorts[0].id
        XCTAssertTrue(review.canRunOrReattach)
        review.cohorts[0].consumedBy = "different-council:cohort:" + review.cohorts[0].id
        XCTAssertFalse(review.canRunOrReattach)
        XCTAssertThrowsError(try review.launchPayload())
    }

    func testDenialNeverDispatchesCouncil() throws {
        let stub = CouncilRuntimeStub()
        let coordinator = CAPTCouncilCoordinator(client: stub)
        var review = try review()
        for index in review.cohorts.indices {
            review.cohorts[index] = try coordinator.requestApproval(review, at: index)
        }
        review.cohorts[0] = try coordinator.decide(review.cohorts[0], approve: false)
        review.cohorts[1] = try coordinator.decide(review.cohorts[1], approve: true)
        XCTAssertFalse(review.canRunOrReattach)
        XCTAssertThrowsError(try coordinator.run(review))
        XCTAssertFalse(stub.calls.contains { $0.0 == "run_approved_council_inspection" })
    }
}
