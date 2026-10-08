import Foundation

/// Bot identity/policy is durable, but creation grants no tools, secrets or
/// autonomous execution. RuntimeService owns authority and persistence.
public struct CAPTBotDraft: Sendable, Equatable {
    public var identifier: String
    public var displayName: String
    public var role: String
    public var roleKind: String
    public var model: String
    public var locality: String
    public var allowCloud: Bool

    public init(identifier: String, displayName: String, role: String,
                roleKind: String = "crew", model: String = "",
                locality: String = "either", allowCloud: Bool = false) {
        self.identifier = identifier
        self.displayName = displayName
        self.role = role
        self.roleKind = roleKind
        self.model = model
        self.locality = locality
        self.allowCloud = allowCloud
    }

    public func payload() throws -> [String: Any] {
        let allowed = CharacterSet(charactersIn: "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.:-")
        guard !identifier.isEmpty,
              identifier.rangeOfCharacter(from: allowed.inverted) == nil,
              !displayName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              !role.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              ["crew", "delegate"].contains(roleKind),
              roleKind != "delegate", // requires a persisted mission binding
              ["local", "cloud", "either"].contains(locality),
              identifier.count <= 100, displayName.count <= 256,
              role.count <= 128, model.count <= 256 else {
            throw CAPTRuntimeClientError.malformedResponse("Invalid Bot identity or policy")
        }
        return ["bot": [
            "schemaVersion": "1.0.0",
            "botId": identifier,
            "displayName": displayName.trimmingCharacters(in: .whitespacesAndNewlines),
            "roleKind": roleKind,
            "role": role.trimmingCharacters(in: .whitespacesAndNewlines),
            "missionId": NSNull(),
            "modelStrategy": [
                "primary": model.isEmpty ? NSNull() : model as Any,
                "fallbacks": [String](),
            ],
            "cognitionPolicy": ["promotionMode": "governed"],
            "localityPolicy": [
                "defaultRuntime": locality,
                "privateData": allowCloud ? "cloud_allowed" : "local_only",
            ],
            "collaboration": ["mayDelegate": false, "maxSpawnDepth": 0],
            "authorityTemplateRef": NSNull(),
        ]]
    }
}

public final class CAPTBotRegistration {
    private let client: CAPTRuntimeCommanding

    public init(client: CAPTRuntimeCommanding) { self.client = client }

    public func register(_ draft: CAPTBotDraft) throws -> String {
        let response = try client.command(
            op: "register_bot",
            payload: try draft.payload(),
            idempotencyKey: "native-create-bot:" + draft.identifier
        )
        guard ["accepted", "idempotent"].contains(response["status"] as? String ?? ""),
              let result = response["result"] as? [String: Any],
              result["botId"] as? String == draft.identifier,
              result["identityOnly"] as? Bool == true else {
            throw CAPTRuntimeClientError.malformedResponse(
                "RuntimeService refused Bot registration: " +
                String(describing: response["error"] ?? "unknown")
            )
        }
        return draft.identifier
    }
}
