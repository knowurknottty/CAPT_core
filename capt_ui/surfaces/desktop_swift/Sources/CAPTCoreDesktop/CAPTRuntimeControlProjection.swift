import Foundation

public struct CAPTMemoryRuntimeSnapshot: Hashable {
    public let active: Bool
    public let policyVersion: Int
    public let policyDigest: String
    public let triggerIntervalTokens: Int
    public let triggerCount: Int
    public let policyVersions: [Int]
    public let lastContextPackDigest: String?
    public let lastContextPackID: String?
    public let selectedRecordCount: Int
    public let unresolvedConflictCount: Int
}

public struct CAPTCheckpointSnapshot: Hashable {
    public let status: String
    public let checkpointID: String
    public let createdAt: String
    public let ledgerSequence: Int
    public let ledgerDigest: String
    public let integrityDigest: String
}
public enum CAPTRuntimeControlProjection {
    public static func memory(
        policy: [String: Any], state: [String: Any]
    ) -> CAPTMemoryRuntimeSnapshot {
        let pack = state["lastContextPack"] as? [String: Any]
        let selected = pack?["selectedRecords"] as? [[String: Any]] ?? []
        let conflicts = pack?["unresolvedConflicts"] as? [[String: Any]] ?? []
        return CAPTMemoryRuntimeSnapshot(
            active: state["memoryPathActive"] as? Bool ?? false,
            policyVersion: policy["policyVersion"] as? Int ?? 0,
            policyDigest: policy["policyDigest"] as? String ?? "",
            triggerIntervalTokens: policy["triggerIntervalTokens"] as? Int ?? 0,
            triggerCount: (state["triggerLog"] as? [[String: Any]])?.count ?? 0,
            policyVersions: state["policyVersions"] as? [Int] ?? [],
            lastContextPackDigest: pack?["contextPackDigest"] as? String,
            lastContextPackID: pack?["contextPackId"] as? String,
            selectedRecordCount: selected.count,
            unresolvedConflictCount: conflicts.count
        )
    }
    public static func checkpoint(_ receipt: [String: Any]) -> CAPTCheckpointSnapshot? {
        guard let result = receipt["result"] as? [String: Any],
              let checkpointID = result["checkpointId"] as? String else { return nil }
        let position = result["ledgerPosition"] as? [String: Any]
        return CAPTCheckpointSnapshot(
            status: receipt["status"] as? String ?? "unknown",
            checkpointID: checkpointID,
            createdAt: result["createdAt"] as? String ?? "",
            ledgerSequence: position?["globalSequence"] as? Int ?? receipt["ledgerHead"] as? Int ?? 0,
            ledgerDigest: result["ledgerDigest"] as? String ?? "",
            integrityDigest: result["integrityDigest"] as? String ?? ""
        )
    }
}
