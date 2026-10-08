import Foundation

/// Runtime-advertised, model-specific media capability. All fields come from
/// the exact validated operator-owned media route registry.
public struct CAPTMediaRouteDescriptor: Identifiable, Equatable, Sendable {
    public var id: String { adapterID }
    public let adapterID: String
    public let provider: String
    public let model: String
    public let operation: String
    public let mediaTypes: [String]
    public let transport: String
    public let maximumPriceUSD: Double

    public init(dictionary: [String: Any]) throws {
        func string(_ key: String) throws -> String {
            guard let value = dictionary[key] as? String, !value.isEmpty else {
                throw CAPTRuntimeClientError.malformedResponse("Media route missing " + key)
            }
            return value
        }
        adapterID = try string("adapterId")
        provider = try string("provider")
        model = try string("model")
        operation = try string("operation")
        transport = try string("transport")
        mediaTypes = dictionary["mediaTypes"] as? [String] ?? []
        maximumPriceUSD = (dictionary["maximumPriceUSD"] as? NSNumber)?.doubleValue ?? 0
    }

    public var displayName: String {
        provider + " / " + model + " · " + operation.replacingOccurrences(of: "_", with: " ")
    }

    public func supports(_ attachments: [CAPTNativeAttachment]) -> Bool {
        switch operation {
        case "image_input":
            return !attachments.isEmpty && attachments.count <= 8 &&
                attachments.allSatisfy { $0.kind == .image }
        case "document_input":
            return !attachments.isEmpty && attachments.count <= 8 &&
                attachments.allSatisfy { $0.mediaType == "application/pdf" }
        case "video_input":
            return !attachments.isEmpty && attachments.count <= 8 &&
                attachments.allSatisfy { $0.mediaType == "video/mp4" }
        case "audio_transcribe":
            return attachments.count == 1 && attachments.first?.kind == .audio
        case "image_generate", "audio_generate", "video_generate":
            return attachments.isEmpty
        default:
            return false
        }
    }
}
