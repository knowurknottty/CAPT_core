import Foundation
import CryptoKit
import UniformTypeIdentifiers

/// Typed, private local intake record. A record is NOT a provider-upload,
/// HumanApproval, ToolBroker read grant, or model-consumed attachment.
public struct CAPTNativeAttachment: Codable, Equatable, Identifiable, Sendable {
    public enum Kind: String, Codable, Sendable {
        case image, video, audio, document, archive, binary
    }

    public let id: UUID
    public let originalName: String
    public let stagedPath: String
    public let sizeBytes: Int64
    public let sha256: String
    public let mediaType: String
    public let kind: Kind
    public let admittedAt: Date

    public var sizeLabel: String {
        ByteCountFormatter.string(fromByteCount: sizeBytes, countStyle: .file)
    }
}

/// Stage *any regular file type* without loading complete video/audio files
/// into memory. Explicitly keeps bytes local, quarantined and unexecuted.
/// Future provider adapters must separately obtain governed upload authority.
public enum CAPTNativeAttachmentStager {
    public static let maxSingleFileBytes: Int64 = 2 * 1024 * 1024 * 1024

    public enum Failure: Error, LocalizedError {
        case notRegularFile, tooLarge, cannotStage, invalidSession, invalidStagingPath

        public var errorDescription: String? {
            switch self {
            case .notRegularFile: return "Only regular files are supported; symbolic links and directories are refused."
            case .tooLarge: return "This file exceeds the current 2 GiB local intake limit."
            case .cannotStage: return "Could not prepare a private local copy of the selected file."
            case .invalidSession: return "Invalid attachment session."
            case .invalidStagingPath: return "Attachment is not in the approved local intake folder."
            }
        }
    }

    public static func defaultRoot() -> URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".capt/native-media-intake/v1", isDirectory: true)
    }

    public static func kind(for source: URL) -> CAPTNativeAttachment.Kind {
        let ext = source.pathExtension.lowercased()
        guard let type = UTType(filenameExtension: ext) else { return .binary }
        if type.conforms(to: .image) { return .image }
        if type.conforms(to: .movie) || type.conforms(to: .video) { return .video }
        if type.conforms(to: .audio) { return .audio }
        if type.conforms(to: .archive) { return .archive }
        if type.conforms(to: .text) || type.conforms(to: .pdf) ||
            type.conforms(to: .spreadsheet) || type.conforms(to: .presentation) ||
            type.conforms(to: .sourceCode) { return .document }
        return .binary
    }

    public static func stage(
        source: URL, sessionID: UUID, root: URL = defaultRoot(),
        maxBytes: Int64 = maxSingleFileBytes
    ) throws -> CAPTNativeAttachment {
        let scoped = source.startAccessingSecurityScopedResource()
        defer { if scoped { source.stopAccessingSecurityScopedResource() } }
        let attributes = try source.resourceValues(forKeys: [
            .isSymbolicLinkKey, .isRegularFileKey, .fileSizeKey
        ])
        guard attributes.isSymbolicLink != true,
              attributes.isRegularFile == true else { throw Failure.notRegularFile }
        guard let size = attributes.fileSize, size >= 0,
              Int64(size) <= maxBytes else { throw Failure.tooLarge }

        let folder = root.appendingPathComponent(sessionID.uuidString.lowercased(), isDirectory: true)
        try FileManager.default.createDirectory(
            at: folder, withIntermediateDirectories: true,
            attributes: [.posixPermissions: 0o700]
        )
        try FileManager.default.setAttributes([.posixPermissions: 0o700], ofItemAtPath: folder.path)

        let safeBase = source.deletingPathExtension().lastPathComponent
            .unicodeScalars.map { scalar -> Character in
                CharacterSet.alphanumerics.contains(scalar) || scalar == "-" || scalar == "_"
                    ? Character(String(scalar)) : "_"
            }
        let prefix = String(safeBase.prefix(60))
        let safeExtension = String(source.pathExtension.unicodeScalars.filter {
            CharacterSet.alphanumerics.contains($0)
        }.prefix(16))
        let id = UUID()
        let baseName = id.uuidString.lowercased() + "-" + (prefix.isEmpty ? "attachment" : prefix)
        let name = safeExtension.isEmpty ? baseName : baseName + "." + safeExtension
        let destination = folder.appendingPathComponent(name, isDirectory: false)
        guard FileManager.default.createFile(atPath: destination.path, contents: nil) else {
            throw Failure.cannotStage
        }
        do {
            try FileManager.default.setAttributes([.posixPermissions: 0o600],
                                                  ofItemAtPath: destination.path)
            let reader = try FileHandle(forReadingFrom: source)
            let writer = try FileHandle(forWritingTo: destination)
            defer { try? reader.close(); try? writer.close() }
            var hasher = SHA256()
            var length: Int64 = 0
            while true {
                let chunk = try reader.read(upToCount: 1_048_576) ?? Data()
                if chunk.isEmpty { break }
                length += Int64(chunk.count)
                guard length <= maxBytes else { throw Failure.tooLarge }
                hasher.update(data: chunk)
                try writer.write(contentsOf: chunk)
            }
            guard length == Int64(size) else { throw Failure.cannotStage }
            let hex = hasher.finalize().map { String(format: "%02x", $0) }.joined()
            let ext = source.pathExtension.lowercased()
            let type = UTType(filenameExtension: ext)
            let record = CAPTNativeAttachment(
                id: id, originalName: source.lastPathComponent,
                stagedPath: destination.path, sizeBytes: length,
                sha256: "sha256:" + hex,
                mediaType: type?.preferredMIMEType ?? "application/octet-stream",
                kind: kind(for: source), admittedAt: Date()
            )
            return record
        } catch {
            try? FileManager.default.removeItem(at: destination)
            throw error
        }
    }

    /// Only delete paths inside the session-controlled intake subtree.
    public static func discard(
        _ attachment: CAPTNativeAttachment,
        sessionID: UUID, root: URL = defaultRoot()
    ) throws {
        let folder = root.appendingPathComponent(sessionID.uuidString.lowercased(), isDirectory: true)
            .standardizedFileURL.resolvingSymlinksInPath()
        let candidate = URL(fileURLWithPath: attachment.stagedPath)
            .standardizedFileURL.resolvingSymlinksInPath()
        guard candidate.deletingLastPathComponent() == folder,
              candidate.lastPathComponent.hasPrefix(attachment.id.uuidString.lowercased() + "-")
        else { throw Failure.invalidStagingPath }
        try FileManager.default.removeItem(at: candidate)
    }
}
