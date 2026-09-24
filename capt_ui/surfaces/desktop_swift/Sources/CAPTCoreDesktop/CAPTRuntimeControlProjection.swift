import Foundation

public struct CAPTRuntimeIdentitySnapshot: Hashable, Sendable {
    public let runtimeVersion: String
    public let integrity: String
    public let headSequence: Int
}

public struct CAPTMemoryRuntimeSnapshot: Hashable, Sendable {
    public let active: Bool
    public let policyVersion: Int
    public let policyDigest: String
    public let triggerIntervalTokens: Int
    public let triggerCount: Int
    public let retrievalTriggerSteps: Int
    public let compressionTriggerSteps: Int
    public let checkpointTriggerSteps: Int
    public let consolidationTriggerSteps: Int
    public let hardStopTriggerSteps: Int
    public let modelSafeLimitSteps: Int
    public let policyVersions: [Int]
    public let lastContextPackDigest: String?
    public let lastContextPackID: String?
    public let selectedRecordCount: Int
    public let unresolvedConflictCount: Int
}

public struct CAPTCheckpointSnapshot: Hashable, Sendable {
    public let status: String
    public let checkpointID: String
    public let createdAt: String
    public let ledgerSequence: Int
    public let ledgerDigest: String
    public let integrityDigest: String
}

public struct CAPTRuntimeCapabilitiesSnapshot: Hashable, Sendable {
    public let queryOperations: [String]
    public let commandOperations: [String]
    public let activeComponents: [String]
    public let lifecycleOperations: [String]

    public func supportsCommand(_ operation: String) -> Bool {
        commandOperations.contains(operation)
    }

    public func supportsQuery(_ operation: String) -> Bool {
        queryOperations.contains(operation)
    }
}


public struct CAPTBotSummary: Identifiable, Hashable, Sendable {
    public let id: String
    public let displayName: String
    public let roleKind: String
    public let role: String
    public let missionID: String?
    public let primaryModel: String?
    public let fallbackModels: [String]
    public let promotionMode: String
    public let defaultRuntime: String
    public let privateData: String
    public let mayDelegate: Bool
    public let maxSpawnDepth: Int
    public let authorityTemplateRef: String?
    public let createdAt: String?
}

public struct CAPTBotSnapshot: Hashable, Sendable {
    public let bots: [CAPTBotSummary]
    public let countsByRoleKind: [String: Int]
    public let note: String
}

public struct CAPTClaimReviewSnapshot: Hashable, Sendable {
    public let claimID: String
    public let guardVerdict: String
    public let guardAdvisory: Bool
    public let guardCommitted: Bool
    public let verificationStatus: String
    public let verificationTrust: String
}

public enum CAPTRuntimeControlProjection {
    public static func identity(_ response: [String: Any]) -> CAPTRuntimeIdentitySnapshot {
        let result = response["result"] as? [String: Any] ?? response
        return CAPTRuntimeIdentitySnapshot(
            runtimeVersion: result["runtimeVersion"] as? String ?? "CAPT",
            integrity: result["integrity"] as? String ?? "unknown",
            headSequence: result["headSequence"] as? Int ?? 0
        )
    }

    public static func bots(_ result: [String: Any]) -> CAPTBotSnapshot {
        let raw = result["bots"] as? [[String: Any]] ?? []
        let bots = raw.compactMap { item -> CAPTBotSummary? in
            guard let id = item["botId"] as? String, !id.isEmpty else { return nil }
            return CAPTBotSummary(
                id: id,
                displayName: item["displayName"] as? String ?? id,
                roleKind: item["roleKind"] as? String ?? "unknown",
                role: item["role"] as? String ?? "",
                missionID: item["missionId"] as? String,
                primaryModel: item["primaryModel"] as? String,
                fallbackModels: item["fallbackModels"] as? [String] ?? [],
                promotionMode: item["promotionMode"] as? String ?? "unknown",
                defaultRuntime: item["defaultRuntime"] as? String ?? "unknown",
                privateData: item["privateData"] as? String ?? "unknown",
                mayDelegate: item["mayDelegate"] as? Bool ?? false,
                maxSpawnDepth: item["maxSpawnDepth"] as? Int ?? 0,
                authorityTemplateRef: item["authorityTemplateRef"] as? String,
                createdAt: item["createdAt"] as? String
            )
        }
        return CAPTBotSnapshot(
            bots: bots,
            countsByRoleKind: result["countsByRoleKind"] as? [String: Int] ?? [:],
            note: result["note"] as? String ?? ""
        )
    }

    public static func claimReview(
        claimID: String, guardResult: [String: Any], verification: [String: Any]
    ) -> CAPTClaimReviewSnapshot {
        let status = verification["status"] as? [String: Any] ?? [:]
        return CAPTClaimReviewSnapshot(
            claimID: claimID,
            guardVerdict: guardResult["verdict"] as? String ?? "unknown",
            guardAdvisory: guardResult["advisory"] as? Bool ?? false,
            guardCommitted: guardResult["committed"] as? Bool ?? false,
            verificationStatus: status["kind"] as? String ?? "unknown",
            verificationTrust: verification["trust"] as? String ?? "unknown"
        )
    }

    public static func capabilities(_ result: [String: Any]) -> CAPTRuntimeCapabilitiesSnapshot {
        let components = result["runtimeComponents"] as? [String: Any] ?? [:]
        let lifecycle = result["lifecycleOperations"] as? [String: Any] ?? [:]
        return CAPTRuntimeCapabilitiesSnapshot(
            queryOperations: result["queryOperations"] as? [String] ?? [],
            commandOperations: result["commandOperations"] as? [String] ?? [],
            activeComponents: components.compactMap { key, value in
                (value as? Bool) == true ? key : nil
            }.sorted(),
            lifecycleOperations: lifecycle.compactMap { key, value in
                (value as? Bool) == true ? key : nil
            }.sorted()
        )
    }

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
            retrievalTriggerSteps: policy["retrievalTriggerSteps"] as? Int ?? 0,
            compressionTriggerSteps: policy["compressionTriggerSteps"] as? Int ?? 0,
            checkpointTriggerSteps: policy["checkpointTriggerSteps"] as? Int ?? 0,
            consolidationTriggerSteps: policy["consolidationTriggerSteps"] as? Int ?? 0,
            hardStopTriggerSteps: policy["hardStopTriggerSteps"] as? Int ?? 0,
            modelSafeLimitSteps: policy["modelSafeLimitSteps"] as? Int ?? 0,
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
