import Foundation

public struct CAPTMissionSummary: Identifiable, Sendable, Equatable {
    public let id: String
    public let title: String
    public let missionState: String
    public let taskID: String?
    public let taskState: String?
}

public struct CAPTEvidenceSummary: Identifiable, Sendable, Equatable {
    public let id: String
    public let missionID: String?
    public let statement: String
    public let promotionState: String
    public let verificationStatus: String?
    public let guardVerdict: String?
    public let evidenceCount: Int
}

public struct CAPTApprovalSummary: Identifiable, Sendable, Equatable {
    public let id: String
    public let missionID: String
    public let taskID: String
    public let operation: String
    public let capability: String
    public let risk: String
    public let state: String
    public let decision: String?
    public let remainingUses: Int
    public let expiresAt: String
    public let provider: String
    public let model: String
    public let targetRoot: String

    public func isActionable(at date: Date = Date()) -> Bool {
        guard state == "requested", decision == nil, remainingUses > 0 else { return false }
        guard let expiry = Self.parseTimestamp(expiresAt) else { return false }
        return expiry > date
    }

    private static func parseTimestamp(_ value: String) -> Date? {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = formatter.date(from: value) { return date }
        formatter.formatOptions = [.withInternetDateTime]
        return formatter.date(from: value)
    }
}

public struct CAPTEventSummary: Identifiable, Sendable, Equatable {
    public var id: Int { sequence }
    public let sequence: Int
    public let type: String
    public let occurredAt: String
    public let streamID: String
    public let missionID: String?
    public let taskID: String?
    public let actorKind: String
}

public struct CAPTDriverRunSummary: Identifiable, Sendable, Equatable {
    public let id: String
    public let missionID: String
    public let taskID: String
    public let driverID: String
    public let state: String
    public let reconciliationStatus: String
    public let externalRunID: String?
}

public enum CAPTOperatorProjection {
    public static func mission(
        _ state: [String: Any],
        tasks: [[String: Any]]
    ) -> CAPTMissionSummary {
        let missionID = state["missionId"] as? String ?? "unknown-mission"
        let matching = tasks.filter { ($0["missionId"] as? String) == missionID }
        let task = matching.last
        let title = task?["title"] as? String ?? missionID
        return CAPTMissionSummary(
            id: missionID,
            title: title,
            missionState: state["state"] as? String ?? "unknown",
            taskID: task?["taskId"] as? String,
            taskState: task?["state"] as? String
        )
    }

    public static func evidence(_ claim: [String: Any]) -> CAPTEvidenceSummary {
        let evidenceIDs = claim["evidenceIds"] as? [Any] ?? []
        return CAPTEvidenceSummary(
            id: claim["claimId"] as? String ?? "unknown-claim",
            missionID: claim["missionId"] as? String,
            statement: claim["statement"] as? String ?? "",
            promotionState: claim["promotionState"] as? String ?? "unknown",
            verificationStatus: stringOrNil(claim["verificationStatus"]),
            guardVerdict: stringOrNil(claim["guardVerdict"]),
            evidenceCount: evidenceIDs.count
        )
    }

    public static func approval(_ raw: [String: Any]) -> CAPTApprovalSummary {
        let scope = raw["scope"] as? [String: Any] ?? [:]
        let binding = scope["approvalBinding"] as? [String: Any] ?? [:]
        return CAPTApprovalSummary(
            id: raw["requestId"] as? String ?? "unknown-approval",
            missionID: raw["missionId"] as? String ?? "",
            taskID: raw["taskId"] as? String ?? "",
            operation: raw["operation"] as? String ?? "",
            capability: raw["requestedCapability"] as? String ?? "",
            risk: raw["riskClassification"] as? String ?? "unknown",
            state: raw["state"] as? String ?? "unknown",
            decision: stringOrNil(raw["decision"]),
            remainingUses: raw["remainingUses"] as? Int ?? 0,
            expiresAt: raw["expiresAt"] as? String ?? "",
            provider: binding["provider"] as? String ?? "",
            model: binding["model"] as? String ?? "",
            targetRoot: binding["targetRoot"] as? String ?? scope["rootPath"] as? String ?? ""
        )
    }

    public static func driverRun(_ raw: [String: Any]) -> CAPTDriverRunSummary {
        CAPTDriverRunSummary(
            id: raw["driverRunId"] as? String ?? "unknown-driver-run",
            missionID: raw["missionId"] as? String ?? "",
            taskID: raw["taskId"] as? String ?? "",
            driverID: raw["driverId"] as? String ?? "unknown",
            state: raw["state"] as? String ?? "unknown",
            reconciliationStatus: raw["reconciliationStatus"] as? String ?? "unknown",
            externalRunID: stringOrNil(raw["externalRunId"])
        )
    }

    public static func event(_ raw: [String: Any]) -> CAPTEventSummary {
        let actor = raw["actor"] as? [String: Any] ?? [:]
        return CAPTEventSummary(
            sequence: raw["globalSequence"] as? Int ?? 0,
            type: raw["eventType"] as? String ?? "UnknownEvent",
            occurredAt: raw["occurredAt"] as? String ?? "",
            streamID: raw["streamId"] as? String ?? "",
            missionID: stringOrNil(raw["missionId"]),
            taskID: stringOrNil(raw["taskId"]),
            actorKind: actor["kind"] as? String ?? "unknown"
        )
    }

    private static func stringOrNil(_ value: Any?) -> String? {
        guard let value, !(value is NSNull) else { return nil }
        return value as? String
    }
}

public struct CAPTHistorySnapshot: Sendable, Equatable {
    public let missions: [CAPTMissionSummary]
    public let evidence: [CAPTEvidenceSummary]
    public let approvals: [CAPTApprovalSummary]
    public let driverRuns: [CAPTDriverRunSummary]
    public let events: [CAPTEventSummary]

    public init(
        missions: [CAPTMissionSummary],
        evidence: [CAPTEvidenceSummary],
        approvals: [CAPTApprovalSummary],
        driverRuns: [CAPTDriverRunSummary],
        events: [CAPTEventSummary]
    ) {
        self.missions = missions
        self.evidence = evidence
        self.approvals = approvals
        self.driverRuns = driverRuns
        self.events = events
    }
}
