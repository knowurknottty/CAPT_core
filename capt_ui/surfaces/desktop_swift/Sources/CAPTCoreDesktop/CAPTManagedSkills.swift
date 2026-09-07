import Foundation

public struct CAPTManagedSkill: Identifiable, Sendable, Equatable {
    public var id: String { name }
    public let name: String
    public let description: String
    public let version: String
    public let contentDigest: String
    public let triggers: [String]
}

public struct CAPTManagedSkillSnapshot: Sendable, Equatable {
    public let installed: Bool
    public let packRoot: String
    public let packName: String
    public let packVersion: String?
    public let manifestDigest: String?
    public let trust: String?
    public let skills: [CAPTManagedSkill]

    public init(dictionary: [String: Any]) throws {
        guard let installed = dictionary["installed"] as? Bool,
              let packRoot = dictionary["packRoot"] as? String,
              let packName = dictionary["packName"] as? String else {
            throw CAPTRuntimeClientError.malformedResponse("managed skills snapshot missing identity")
        }
        self.installed = installed
        self.packRoot = packRoot
        self.packName = packName
        self.packVersion = dictionary["packVersion"] as? String
        self.manifestDigest = dictionary["manifestDigest"] as? String
        self.trust = dictionary["trust"] as? String
        let raw = dictionary["skills"] as? [[String: Any]] ?? []
        skills = raw.compactMap { item in
            guard let name = item["name"] as? String,
                  let digest = item["contentDigest"] as? String else { return nil }
            return CAPTManagedSkill(
                name: name,
                description: item["description"] as? String ?? "",
                version: item["version"] as? String ?? "0.0.0",
                contentDigest: digest,
                triggers: item["triggers"] as? [String] ?? []
            )
        }
    }
}
