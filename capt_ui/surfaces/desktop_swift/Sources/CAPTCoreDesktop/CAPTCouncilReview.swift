import Foundation

/// Native presentation state for one governed council in one chat.
public struct CAPTCouncilCohort: Codable, Equatable, Identifiable, Sendable {
    public let id: String
    public let provider: String
    public let model: String
    public let vessels: Int
    public var requestID: String?
    public var taskID: String?
    public var driverRunID: String?
    public var expiresAt: String?
    public var consumedBy: String?
    public var state: String

    public init(id: String, provider: String, model: String, vessels: Int) {
        self.id = id
        self.provider = provider
        self.model = model
        self.vessels = vessels
        self.state = "unprepared"
    }
}

public struct CAPTCouncilReview: Codable, Equatable, Identifiable, Sendable {
    public let id: String
    public let missionID: String
    public let objective: String
    public let targetRoot: String
    public let maxConcurrentCohorts: Int
    public var cohorts: [CAPTCouncilCohort]
    public var executionReceipt: String?
    public var message: String?

    public init(
        id: String, missionID: String, objective: String, targetRoot: String,
        maxConcurrentCohorts: Int, cohorts: [CAPTCouncilCohort]
    ) throws {
        guard !objective.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              !targetRoot.isEmpty,
              (1...24).contains(cohorts.count),
              (1...cohorts.count).contains(maxConcurrentCohorts),
              Set(cohorts.map(\.id)).count == cohorts.count,
              Set(cohorts.map(\.vessels)).count == 1,
              cohorts.allSatisfy({ (1...1000).contains($0.vessels) &&
                  !$0.provider.isEmpty && !$0.model.isEmpty }) else {
            throw CAPTRuntimeClientError.malformedResponse("invalid council cohort configuration")
        }
        self.id = id
        self.missionID = missionID
        self.objective = objective
        self.targetRoot = targetRoot
        self.maxConcurrentCohorts = maxConcurrentCohorts
        self.cohorts = cohorts
    }

    public var allApproved: Bool {
        !cohorts.isEmpty && cohorts.allSatisfy { $0.state == "approved" && $0.requestID != nil }
    }

    /// Resume only the original dispatch lineage, never a new inference attempt.
    public var canRunOrReattach: Bool {
        executionReceipt == nil && !cohorts.isEmpty && cohorts.allSatisfy { cohort in
            guard cohort.requestID != nil else { return false }
            if cohort.state == "consumed" {
                return cohort.consumedBy == "native-council:" + id + ":run:cohort:" + cohort.id
            }
            guard cohort.state == "approved" else { return false }
            guard let expiresAt = cohort.expiresAt else { return false }
            let parser = ISO8601DateFormatter()
            parser.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            let deadline = parser.date(from: expiresAt) ?? ISO8601DateFormatter().date(from: expiresAt)
            return deadline.map { $0 > Date() } ?? false
        }
    }

    public func approvalPayload(at index: Int) -> [String: Any] {
        let cohort = cohorts[index]
        return [
            "objective": objective,
            "targetRoot": targetRoot,
            "provider": cohort.provider,
            "model": cohort.model,
            "missionId": missionID,
            "taskId": "t-" + id + "-" + cohort.id,
            "driverRunId": "dr-" + id + "-" + cohort.id,
            "requestedContextBudget": 128_000,
            "requestedExecutionSeconds": 1800,
            "humanVerificationRequired": true,
            "responseMode": "SPOCK",
            "promptEnhancement": "OFF",
            "cohortSpec": [
                "cohortId": cohort.id,
                "vesselsPerCohort": cohort.vessels,
                "configurationId": "native-council-v2",
                "vesselCharterPolicy": ["schemaVersion": "2.0.0"],
            ],
            "authorityProfile": [
                "filesystemScope": "project",
                "filesystemRoot": targetRoot,
                "fileMutationAllowed": false,
                "shellAccessAllowed": false,
                "providerNetworkPolicy": "remote_allowed",
            ],
        ]
    }

    public func launchPayload() throws -> [String: Any] {
        guard canRunOrReattach else {
            throw CAPTRuntimeClientError.malformedResponse("council not fully approved or already executed")
        }
        let executions: [[String: Any]] = try cohorts.indices.map { index in
            let cohort = cohorts[index]
            guard let requestID = cohort.requestID,
                  let taskID = cohort.taskID, let runID = cohort.driverRunID else {
                throw CAPTRuntimeClientError.malformedResponse("cohort approval identity missing")
            }
            var payload = approvalPayload(at: index)
            payload["approvalRequestId"] = requestID
            payload["taskId"] = taskID
            payload["driverRunId"] = runID
            return payload
        }
        return [
            "councilId": id,
            "maxConcurrentCohorts": maxConcurrentCohorts,
            "executions": executions,
        ]
    }
}
