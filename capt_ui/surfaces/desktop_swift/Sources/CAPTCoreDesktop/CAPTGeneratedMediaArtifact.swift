import Foundation
import CryptoKit

/// Previewable local provider result, not accepted/verified task evidence.
/// Never opens a URL returned by a model or provider without local digest proof.
public struct CAPTGeneratedMediaArtifact: Equatable, Sendable {
    public let path: String
    public let mediaType: String
    public let artifactDigest: String
    public let byteCount: Int64
    public let kind: CAPTNativeAttachment.Kind
}

public enum CAPTGeneratedMediaLocator {
    /// Bounded parse + trust-root + bytes/digest check. No network requests.
    /// Artifact provenance remains "untrusted" until independent verification.
    public static func inspect(
        detailsJSON: String,
        allowedRoots: [URL],
        maxBytes: Int64 = 2 * 1024 * 1024 * 1024
    ) -> CAPTGeneratedMediaArtifact? {
        guard detailsJSON.utf8.count <= 2_000_000,
              let data = detailsJSON.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data),
              let candidate = firstCandidate(in: json, depth: 0),
              let path = candidate["artifactPath"] as? String,
              let digest = candidate["artifactDigest"] as? String,
              let mediaType = candidate["mediaType"] as? String,
              digest.hasPrefix("sha256:"),
              digest.count == 71,
              path.hasPrefix("/"),
              let kind = kind(for: mediaType)
        else { return nil }

        let file = URL(fileURLWithPath: path).standardizedFileURL
        guard file.resolvingSymlinksInPath() == file,
              allowedRoots.contains(where: { root in
                  let base = root.standardizedFileURL.resolvingSymlinksInPath().path
                  return file.path.hasPrefix(base + "/")
              }),
              let attr = try? file.resourceValues(forKeys: [
                .isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey
              ]),
              attr.isRegularFile == true, attr.isSymbolicLink != true,
              let size = attr.fileSize, size >= 0,
              Int64(size) <= maxBytes,
              let handle = try? FileHandle(forReadingFrom: file)
        else { return nil }
        defer { try? handle.close() }
        var hasher = SHA256()
        var counted: Int64 = 0
        do {
            while true {
                let bytes = try handle.read(upToCount: 1_048_576) ?? Data()
                if bytes.isEmpty { break }
                counted += Int64(bytes.count)
                if counted > maxBytes { return nil }
                hasher.update(data: bytes)
            }
        } catch { return nil }
        guard counted == Int64(size) else { return nil }
        let calculated = "sha256:" +
            hasher.finalize().map { String(format: "%02x", $0) }.joined()
        guard digest.lowercased() == calculated else { return nil }
        return CAPTGeneratedMediaArtifact(
            path: file.path, mediaType: mediaType,
            artifactDigest: calculated, byteCount: counted, kind: kind
        )
    }

    private static func kind(for mime: String) -> CAPTNativeAttachment.Kind? {
        if mime.hasPrefix("image/") { return .image }
        if mime.hasPrefix("audio/") { return .audio }
        if mime.hasPrefix("video/") { return .video }
        return nil
    }

    private static func firstCandidate(
        in value: Any, depth: Int
    ) -> [String: Any]? {
        guard depth <= 7 else { return nil }
        if let object = value as? [String: Any] {
            if let result = object["artifactCandidate"] as? [String: Any] {
                return result
            }
            for (_, nested) in object {
                if let found = firstCandidate(in: nested, depth: depth + 1) {
                    return found
                }
            }
        } else if let list = value as? [Any] {
            for nested in list.prefix(32) {
                if let found = firstCandidate(in: nested, depth: depth + 1) {
                    return found
                }
            }
        }
        return nil
    }
}
