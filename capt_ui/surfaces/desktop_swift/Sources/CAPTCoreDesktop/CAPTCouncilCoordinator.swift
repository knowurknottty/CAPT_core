import Foundation

/// RuntimeService remains the sole authority for council approvals and dispatch.
public final class CAPTCouncilCoordinator {
    private let client: CAPTRuntimeCommanding

    public init(client: CAPTRuntimeCommanding) {
        self.client = client
    }

    private static func accepted(_ receipt: [String: Any]) throws -> [String: Any] {
        guard ["accepted", "idempotent"].contains(receipt["status"] as? String ?? "") else {
            let detail = receipt["detail"] as? String ??
                String(describing: receipt["error"] ?? "rejected")
            throw CAPTRuntimeClientError.malformedResponse("Council command rejected: " + detail)
        }
        guard let result = receipt["result"] as? [String: Any] else {
            throw CAPTRuntimeClientError.malformedResponse("Council receipt missing result")
        }
        return result
    }

    public func requestApproval(_ review: CAPTCouncilReview, at index: Int) throws -> CAPTCouncilCohort {
        guard review.cohorts.indices.contains(index) else {
            throw CAPTRuntimeClientError.malformedResponse("invalid council cohort index")
        }
        var cohort = review.cohorts[index]
        guard cohort.requestID == nil else { return cohort }
        let receipt = try client.command(
            op: "request_model_prompt_approval",
            payload: review.approvalPayload(at: index),
            idempotencyKey: "native-council:" + review.id + ":approval:" + cohort.id
        )
        let result = try Self.accepted(receipt)
        guard let requestID = result["requestId"] as? String, !requestID.isEmpty,
              let taskID = result["taskId"] as? String, !taskID.isEmpty,
              let runID = result["driverRunId"] as? String, !runID.isEmpty else {
            throw CAPTRuntimeClientError.malformedResponse("Council approval identity incomplete")
        }
        cohort.requestID = requestID
        cohort.taskID = taskID
        cohort.driverRunID = runID
        cohort.expiresAt = result["expiresAt"] as? String
        cohort.state = "requested"
        return cohort
    }

    public func refreshState(_ cohort: CAPTCouncilCohort) throws -> CAPTCouncilCohort {
        guard let id = cohort.requestID else { return cohort }
        let reply = try client.query(
            op: "get_state",
            payload: ["streamId": "human_approval-" + id]
        )
        guard reply["ok"] as? Bool == true,
              let state = reply["result"] as? [String: Any],
              state["requestId"] as? String == id,
              let storedState = state["state"] as? String else {
            throw CAPTRuntimeClientError.malformedResponse("Council approval state unavailable")
        }
        var next = cohort
        next.state = storedState
        next.consumedBy = state["consumedBy"] as? String
        return next
    }

    public func decide(_ cohort: CAPTCouncilCohort, approve: Bool) throws -> CAPTCouncilCohort {
        guard let id = cohort.requestID else {
            throw CAPTRuntimeClientError.malformedResponse("Council approval not requested")
        }
        let current = try refreshState(cohort)
        guard current.state == "requested" else {
            throw CAPTRuntimeClientError.malformedResponse(
                "Council approval no longer awaiting decision: " + current.state
            )
        }
        let receipt = try client.command(
            op: "submit_approval_decision",
            payload: [
                "requestId": id,
                "decision": approve ? "approve" : "deny",
                "note": "Explicit native macOS council operator decision"
            ],
            idempotencyKey: "native-council:" + id + (approve ? ":approve" : ":deny")
        )
        guard ["accepted", "idempotent"].contains(receipt["status"] as? String ?? "") else {
            throw CAPTRuntimeClientError.malformedResponse("Council decision rejected by RuntimeService")
        }
        return try refreshState(cohort)
    }

    public func run(_ review: CAPTCouncilReview) throws -> String {
        // Never trust cached local labels to authorize an execution.
        for cohort in review.cohorts {
            let live = try refreshState(cohort)
            let exactUseID = "native-council:" + review.id + ":run:cohort:" + cohort.id
            guard live.state == "approved" ||
                    (live.state == "consumed" && live.consumedBy == exactUseID) else {
                throw CAPTRuntimeClientError.malformedResponse(
                    "Council cohort " + cohort.id + " not approved: " + live.state
                )
            }
        }
        let receipt = try client.command(
            op: "run_approved_council_inspection",
            payload: review.launchPayload(),
            idempotencyKey: "native-council:" + review.id + ":run"
        )
        _ = try Self.accepted(receipt)
        let data = try JSONSerialization.data(
            withJSONObject: receipt, options: [.prettyPrinted, .sortedKeys]
        )
        return String(decoding: data, as: UTF8.self)
    }
}
