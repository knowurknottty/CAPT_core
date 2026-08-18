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
    public let events: [CAPTEventSummary]

    public init(
        missions: [CAPTMissionSummary],
        evidence: [CAPTEvidenceSummary],
        events: [CAPTEventSummary]
    ) {
        self.missions = missions
        self.evidence = evidence
        self.events = events
    }
}
