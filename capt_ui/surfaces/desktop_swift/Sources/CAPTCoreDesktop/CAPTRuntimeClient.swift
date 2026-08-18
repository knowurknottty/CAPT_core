import Foundation
import CryptoKit
import Darwin

public enum CAPTRuntimeClientError: Error, LocalizedError {
    case tokenMissing(String)
    case socketPathTooLong(String)
    case socketFailure(String)
    case authenticationFailed(String)
    case malformedResponse(String)
    case frameTooLarge(Int)
    case notAuthenticated

    public var errorDescription: String? {
        switch self {
        case .tokenMissing(let path): return "CAPT runtime token missing at \(path)"
        case .socketPathTooLong(let path): return "Unix socket path too long: \(path)"
        case .socketFailure(let message): return message
        case .authenticationFailed(let message): return "CAPT authentication failed: \(message)"
        case .malformedResponse(let message): return "Malformed CAPT response: \(message)"
        case .frameTooLarge(let length): return "CAPT frame exceeds limit: \(length) bytes"
        case .notAuthenticated: return "CAPT runtime client is not authenticated"
        }
    }
}

public final class CAPTRuntimeClient: CAPTRuntimeCommanding {
    public static let maximumFrameBytes = 4 * 1024 * 1024

    public let socketPath: String
    public let tokenPath: String
    public private(set) var operatorID: String?
    public private(set) var sessionID: String?

    private var socketFD: Int32 = -1
    private let lock = NSLock()

    public init(socketPath: String, tokenPath: String) {
        self.socketPath = socketPath
        self.tokenPath = tokenPath
    }

    public convenience init() {
        let env = ProcessInfo.processInfo.environment
        let stateDirectory: String
        if let override = env["CAPT_STATE_DIR"], !override.isEmpty {
            stateDirectory = NSString(string: override).expandingTildeInPath
        } else {
            stateDirectory = FileManager.default.homeDirectoryForCurrentUser
                .appendingPathComponent(".capt", isDirectory: true).path
        }
        self.init(
            socketPath: URL(fileURLWithPath: stateDirectory)
                .appendingPathComponent("runtime.sock").path,
            tokenPath: URL(fileURLWithPath: stateDirectory)
                .appendingPathComponent("runtime.token").path
        )
    }

    deinit {
        disconnect()
    }

    public func connect() throws -> [String: Any] {
        let tokenURL = URL(fileURLWithPath: tokenPath)
        guard let token = try? String(contentsOf: tokenURL, encoding: .utf8)
            .trimmingCharacters(in: .whitespacesAndNewlines), !token.isEmpty else {
            throw CAPTRuntimeClientError.tokenMissing(tokenPath)
        }
        disconnect()
        socketFD = try Self.openUnixSocket(path: socketPath)
        try send(payload: ["token": token])
        let auth = try receive()
        guard auth["ok"] as? Bool == true else {
            let message = auth["error"] as? String ?? "unknown authentication error"
            disconnect()
            throw CAPTRuntimeClientError.authenticationFailed(message)
        }
        operatorID = auth["operatorId"] as? String
        sessionID = auth["sessionId"] as? String
        guard operatorID != nil, sessionID != nil else {
            disconnect()
            throw CAPTRuntimeClientError.malformedResponse("missing operator/session identity")
        }
        return try query(op: "identity", payload: [:])
    }

    public func disconnect() {
        lock.lock()
        defer { lock.unlock() }
        if socketFD >= 0 {
            Darwin.close(socketFD)
            socketFD = -1
        }
        operatorID = nil
        sessionID = nil
    }

    public func query(op: String, payload: [String: Any] = [:]) throws -> [String: Any] {
        var request = payload
        request["op"] = op
        return try transact(request)
    }

    public func command(
        op: String,
        payload: [String: Any],
        idempotencyKey: String? = nil
    ) throws -> [String: Any] {
        guard let operatorID, let sessionID else {
            throw CAPTRuntimeClientError.notAuthenticated
        }
        let envelope = try Self.makeCommandEnvelope(
            op: op,
            payload: payload,
            operatorID: operatorID,
            sessionID: sessionID,
            idempotencyKey: idempotencyKey,
            correlationID: "corr-" + UUID().uuidString.lowercased(),
            timestamp: Self.currentTimestamp()
        )
        return try transact(["op": "command", "command": envelope])
    }

    public static func makeCommandEnvelope(
        op: String,
        payload: [String: Any],
        operatorID: String,
        sessionID: String,
        idempotencyKey: String? = nil,
        correlationID: String,
        timestamp: String
    ) throws -> [String: Any] {
        let seed = try canonicalJSONData(["op": op, "payload": payload])
        let digest = SHA256.hash(data: seed).map { String(format: "%02x", $0) }.joined()
        let commandID = "cmd-" + String(digest.prefix(16))
        return [
            "commandId": commandID,
            "operatorId": operatorID,
            "sessionId": sessionID,
            "schemaVersion": "1.0.0",
            "correlationId": correlationID,
            "idempotencyKey": idempotencyKey ?? (commandID + "-idem"),
            "timestamp": timestamp,
            "op": op,
            "payload": payload,
        ]
    }

    public static func currentTimestamp() -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        return formatter.string(from: Date())
    }

    public static func makeFrame(_ payload: [String: Any]) throws -> Data {
        let body = try canonicalJSONData(payload)
        try validateFrameLength(body.count)
        var length = UInt32(body.count).bigEndian
        var frame = Data()
        withUnsafeBytes(of: &length) { frame.append(contentsOf: $0) }
        frame.append(body)
        return frame
    }

    public static func validateFrameLength(_ length: Int) throws {
        guard length >= 0, length <= maximumFrameBytes else {
            throw CAPTRuntimeClientError.frameTooLarge(length)
        }
    }

    static func canonicalJSONData(_ payload: [String: Any]) throws -> Data {
        guard JSONSerialization.isValidJSONObject(payload) else {
            throw CAPTRuntimeClientError.malformedResponse("non-JSON command payload")
        }
        return try JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys])
    }

    private func transact(_ payload: [String: Any]) throws -> [String: Any] {
        lock.lock()
        defer { lock.unlock() }
        guard socketFD >= 0 else {
            throw CAPTRuntimeClientError.socketFailure("CAPT runtime socket is not connected")
        }
        try sendUnlocked(payload: payload)
        return try receiveUnlocked()
    }

    private func send(payload: [String: Any]) throws {
        lock.lock()
        defer { lock.unlock() }
        try sendUnlocked(payload: payload)
    }

    private func receive() throws -> [String: Any] {
        lock.lock()
        defer { lock.unlock() }
        return try receiveUnlocked()
    }

    private func sendUnlocked(payload: [String: Any]) throws {
        let frame = try Self.makeFrame(payload)
        var offset = 0
        try frame.withUnsafeBytes { rawBuffer in
            guard let baseAddress = rawBuffer.baseAddress else { return }
            while offset < frame.count {
                let sent = Darwin.send(
                    socketFD,
                    baseAddress.advanced(by: offset),
                    frame.count - offset,
                    0
                )
                if sent <= 0 {
                    throw CAPTRuntimeClientError.socketFailure(
                        "CAPT socket send failed: \(String(cString: strerror(errno)))"
                    )
                }
                offset += sent
            }
        }
    }

    private func receiveUnlocked() throws -> [String: Any] {
        let header = try readExact(4)
        let length = header.withUnsafeBytes { raw -> UInt32 in
            raw.load(as: UInt32.self).bigEndian
        }
        try Self.validateFrameLength(Int(length))
        let body = try readExact(Int(length))
        let object = try JSONSerialization.jsonObject(with: body)
        guard let dictionary = object as? [String: Any] else {
            throw CAPTRuntimeClientError.malformedResponse("top-level JSON is not an object")
        }
        return dictionary
    }

    private func readExact(_ count: Int) throws -> Data {
        var data = Data(count: count)
        var receivedTotal = 0
        try data.withUnsafeMutableBytes { rawBuffer in
            guard let baseAddress = rawBuffer.baseAddress else { return }
            while receivedTotal < count {
                let received = Darwin.recv(
                    socketFD,
                    baseAddress.advanced(by: receivedTotal),
                    count - receivedTotal,
                    0
                )
                if received <= 0 {
                    throw CAPTRuntimeClientError.socketFailure(
                        "CAPT socket closed mid-frame"
                    )
                }
                receivedTotal += received
            }
        }
        return data
    }

    private static func openUnixSocket(path: String) throws -> Int32 {
        var address = sockaddr_un()
        address.sun_family = sa_family_t(AF_UNIX)
        let pathBytes = path.utf8CString
        let capacity = MemoryLayout.size(ofValue: address.sun_path)
        guard pathBytes.count <= capacity else {
            throw CAPTRuntimeClientError.socketPathTooLong(path)
        }

        withUnsafeMutablePointer(to: &address.sun_path) { pointer in
            pointer.withMemoryRebound(to: CChar.self, capacity: capacity) { destination in
                pathBytes.withUnsafeBufferPointer { source in
                    destination.initialize(from: source.baseAddress!, count: pathBytes.count)
                }
            }
        }
        let fd = Darwin.socket(AF_UNIX, SOCK_STREAM, 0)
        guard fd >= 0 else {
            throw CAPTRuntimeClientError.socketFailure(
                "Unable to create CAPT Unix socket: \(String(cString: strerror(errno)))"
            )
        }
        let result = withUnsafePointer(to: &address) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { socketAddress in
                Darwin.connect(fd, socketAddress, socklen_t(MemoryLayout<sockaddr_un>.size))
            }
        }
        guard result == 0 else {
            let message = String(cString: strerror(errno))
            Darwin.close(fd)
            throw CAPTRuntimeClientError.socketFailure(
                "Unable to connect to CAPT runtime at \(path): \(message)"
            )
        }
        return fd
    }
}
