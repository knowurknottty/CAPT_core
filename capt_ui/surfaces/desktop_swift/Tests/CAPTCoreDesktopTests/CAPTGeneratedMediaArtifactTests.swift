import Foundation
import CryptoKit
import XCTest
@testable import CAPTCoreDesktop

final class CAPTGeneratedMediaArtifactTests: XCTestCase {
    private func fixture() throws -> (URL, URL, String) {
        let folder = FileManager.default.temporaryDirectory
            .appendingPathComponent("capt-output-test-" + UUID().uuidString)
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        let file = folder.appendingPathComponent("generated.png")
        let data = Data([137, 80, 78, 71, 13, 10, 26, 10])
        try data.write(to: file)
        let digest = "sha256:" +
            SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
        return (folder, file, digest)
    }

    private func receipt(_ path: String, _ digest: String,
                         mime: String = "image/png") -> String {
        let raw: [String: Any] = [
            "result": ["runnerResult": [
                "artifactCandidate": [
                    "artifactPath": path, "artifactDigest": digest,
                    "mediaType": mime, "artifactKind": "image"
                ]
            ]]
        ]
        let data = try! JSONSerialization.data(withJSONObject: raw)
        return String(data: data, encoding: .utf8)!
    }

    func testDigestVerifiedGeneratedArtifactIsRecognizedWithoutRemoteFetch() throws {
        let (folder, file, digest) = try fixture()
        defer { try? FileManager.default.removeItem(at: folder) }
        let item = CAPTGeneratedMediaLocator.inspect(
            detailsJSON: receipt(file.path, digest), allowedRoots: [folder]
        )
        XCTAssertEqual(item?.kind, .image)
        XCTAssertEqual(item?.mediaType, "image/png")
        XCTAssertEqual(item?.byteCount, 8)
        XCTAssertEqual(item?.artifactDigest, digest)
    }

    func testUntrustedPathAndTamperedBytesRefused() throws {
        let (folder, file, digest) = try fixture()
        defer { try? FileManager.default.removeItem(at: folder) }
        XCTAssertNil(CAPTGeneratedMediaLocator.inspect(
            detailsJSON: receipt(file.path, digest),
            allowedRoots: [folder.appendingPathComponent("elsewhere")]
        ))
        try Data([1,2,3]).write(to: file)
        XCTAssertNil(CAPTGeneratedMediaLocator.inspect(
            detailsJSON: receipt(file.path, digest), allowedRoots: [folder]
        ))
    }

    func testSymbolicLinkCannotSmuggleArtifactFromOutsideRoot() throws {
        let (folder, file, digest) = try fixture()
        defer { try? FileManager.default.removeItem(at: folder) }
        let target = folder.appendingPathComponent("alias.png")
        try FileManager.default.createSymbolicLink(at: target, withDestinationURL: file)
        XCTAssertNil(CAPTGeneratedMediaLocator.inspect(
            detailsJSON: receipt(target.path, digest), allowedRoots: [folder]
        ))
    }
}
