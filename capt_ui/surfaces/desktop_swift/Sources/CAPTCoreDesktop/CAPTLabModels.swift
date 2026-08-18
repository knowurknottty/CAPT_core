import Foundation

public struct CAPTLabOperationSnapshot: Identifiable, Sendable, Equatable, Hashable {
    public var id: String { name }
    public let name: String
    public let epistemicClass: String
    public let description: String
}

public struct CAPTLabSourceFileSnapshot: Identifiable, Sendable, Equatable, Hashable {
    public var id: String { path }
    public let path: String
    public let sha256: String
    public let supplementaryLocalDonor: Bool
}

public struct CAPTLabEngineSnapshot: Identifiable, Sendable, Equatable {
    public let id: String
    public let engineVersion: String
    public let displayName: String
    public let description: String
    public let available: Bool
    public let requiresFilesystem: Bool
    public let requiresNetwork: Bool
    public let operations: [CAPTLabOperationSnapshot]
    public let donorRepository: String
    public let donorCommit: String
    public let sourceFiles: [CAPTLabSourceFileSnapshot]
    public let limitations: [String]
    public let validation: [String]
}

public struct CAPTLabRunReceipt: Sendable, Equatable {
    public let missionID: String
    public let taskID: String
    public let driverRunID: String
    public let claimID: String
    public let evidenceID: String
    public let verificationID: String?
    public let promotionState: String
    public let artifactPath: String
    public let artifactDigest: String
    public let requestDigest: String
    public let engineID: String
    public let operation: String
    public let epistemicClass: String

    public var authorityLabel: String {
        if verificationID != nil && promotionState != "proposed" {
            return "VERIFIED"
        }
        return "UNVERIFIED"
    }
}

public enum CAPTLabProjectionError: Error, LocalizedError {
    case invalidInputJSON
    case inputMustBeObject

    public var errorDescription: String? {
        switch self {
        case .invalidInputJSON:
            return "Lab input is not valid JSON."
        case .inputMustBeObject:
            return "Lab input JSON must have an object at its root."
        }
    }
}

public enum CAPTLabProjection {
    public static func engine(_ raw: [String: Any]) -> CAPTLabEngineSnapshot {
        let operations = (raw["operations"] as? [[String: Any]] ?? []).map { item in
            CAPTLabOperationSnapshot(
                name: item["name"] as? String ?? "unknown",
                epistemicClass: item["epistemicClass"] as? String ?? "advisory",
                description: item["description"] as? String ?? ""
            )
        }
        let provenance = raw["provenance"] as? [String: Any] ?? [:]
        let sourceFiles = (provenance["sourceFiles"] as? [[String: Any]] ?? []).map { item in
            CAPTLabSourceFileSnapshot(
                path: item["path"] as? String ?? "",
                sha256: item["sha256"] as? String ?? "",
                supplementaryLocalDonor: item["supplementaryLocalDonor"] as? Bool ?? false
            )
        }
        return CAPTLabEngineSnapshot(
            id: raw["engineId"] as? String ?? "unknown-engine",
            engineVersion: raw["engineVersion"] as? String ?? "",
            displayName: raw["displayName"] as? String ?? (raw["engineId"] as? String ?? "Lab Engine"),
            description: raw["description"] as? String ?? "",
            available: raw["available"] as? Bool ?? false,
            requiresFilesystem: raw["requiresFilesystem"] as? Bool ?? false,
            requiresNetwork: raw["requiresNetwork"] as? Bool ?? false,
            operations: operations,
            donorRepository: provenance["donorRepository"] as? String ?? "",
            donorCommit: provenance["donorCommit"] as? String ?? "",
            sourceFiles: sourceFiles,
            limitations: provenance["limitations"] as? [String] ?? [],
            validation: provenance["validation"] as? [String] ?? []
        )
    }

    public static func receipt(_ raw: [String: Any]) -> CAPTLabRunReceipt {
        CAPTLabRunReceipt(
            missionID: raw["missionId"] as? String ?? "",
            taskID: raw["taskId"] as? String ?? "",
            driverRunID: raw["driverRunId"] as? String ?? "",
            claimID: raw["claimId"] as? String ?? "",
            evidenceID: raw["evidenceId"] as? String ?? "",
            verificationID: stringOrNil(raw["verificationId"]),
            promotionState: raw["promotionState"] as? String ?? "unknown",
            artifactPath: raw["artifactPath"] as? String ?? "",
            artifactDigest: raw["artifactDigest"] as? String ?? "",
            requestDigest: raw["requestDigest"] as? String ?? "",
            engineID: raw["engineId"] as? String ?? "",
            operation: raw["operation"] as? String ?? "",
            epistemicClass: raw["epistemicClass"] as? String ?? "advisory"
        )
    }

    public static func inputObject(from text: String) throws -> [String: Any] {
        guard let data = text.data(using: .utf8) else {
            throw CAPTLabProjectionError.invalidInputJSON
        }
        let value: Any
        do {
            value = try JSONSerialization.jsonObject(with: data, options: [])
        } catch {
            throw CAPTLabProjectionError.invalidInputJSON
        }
        guard let object = value as? [String: Any] else {
            throw CAPTLabProjectionError.inputMustBeObject
        }
        return object
    }

    private static func stringOrNil(_ value: Any?) -> String? {
        guard let value, !(value is NSNull) else { return nil }
        return value as? String
    }
}
