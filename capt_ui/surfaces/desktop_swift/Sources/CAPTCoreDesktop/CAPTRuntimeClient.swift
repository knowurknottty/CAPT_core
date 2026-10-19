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
    public static let socketIODeadlineSeconds: TimeInterval = 8

    public let socketPath: String
    public let tokenPath: String
    public private(set) var operatorID: String?
    public private(set) var sessionID: String?

    private var socketFD: Int32 = -1
    private let lock = NSLock()
    // Independent from the transaction lock: shutdown can interrupt a
    // blocked recv without waiting for that same transaction to finish.
    private let descriptorLock = NSLock()

    public init(socketPath: String, tokenPath: String) {
        self.socketPath = socketPath
        self.tokenPath = tokenPath
    }

    public convenience init() {
        self.init(profile: CAPTRuntimeProfile.current())
    }

    public convenience init(profile: CAPTRuntimeProfile) {
        self.init(
            socketPath: URL(fileURLWithPath: profile.stateDirectory)
                .appendingPathComponent("runtime.sock").path,
            tokenPath: URL(fileURLWithPath: profile.stateDirectory)
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
        let opened = try Self.openUnixSocket(path: socketPath)
        descriptorLock.lock()
        socketFD = opened
        descriptorLock.unlock()
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
        disconnectUnlocked()
    }

    /// Interrupts a blocked transaction without replaying its command.
    /// The caller must reconcile the original command ID before a fresh effect.
    public func interruptPendingTransaction() {
        descriptorLock.lock()
        defer { descriptorLock.unlock() }
        if socketFD >= 0 {
            _ = Darwin.shutdown(socketFD, SHUT_RDWR)
        }
    }

    private func disconnectUnlocked() {
        descriptorLock.lock()
        if socketFD >= 0 {
            Darwin.close(socketFD)
            socketFD = -1
        }
        descriptorLock.unlock()
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
        // A stale or never-connected desktop client may lose session identity
        // while RuntimeService itself remains healthy. Authenticate before a
        // NEW command only; never replay a command after a send/read failure.
        if operatorID == nil || sessionID == nil {
            _ = try connect()
        }
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
        var identitySeed: [String: Any] = ["op": op, "payload": payload]
        if let idempotencyKey {
            identitySeed["idempotencyKey"] = idempotencyKey
        }
        let seed = try canonicalJSONData(identitySeed)
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
        do {
            try sendUnlocked(payload: payload)
            return try receiveUnlocked()
        } catch {
            disconnectUnlocked()
            throw error
        }
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
        let deadline = ProcessInfo.processInfo.systemUptime + Self.socketIODeadlineSeconds
        var offset = 0
        try frame.withUnsafeBytes { rawBuffer in
            guard let baseAddress = rawBuffer.baseAddress else { return }
            while offset < frame.count {
                try Self.waitForSocket(fd: socketFD, events: Int16(POLLOUT), deadline: deadline)
                let sent = Darwin.send(
                    socketFD,
                    baseAddress.advanced(by: offset),
                    frame.count - offset,
                    0
                )
                if sent < 0 && errno == EINTR { continue }
                if sent <= 0 {
                    throw CAPTRuntimeClientError.socketFailure(
                        "CAPT socket send failed (possible indeterminate command): \(String(cString: strerror(errno)))"
                    )
                }
                offset += sent
            }
        }
    }

    private func receiveUnlocked() throws -> [String: Any] {
        let deadline = ProcessInfo.processInfo.systemUptime + Self.socketIODeadlineSeconds
        let header = try Self.readExactFromSocket(fd: socketFD, count: 4, deadline: deadline)
        let length = header.withUnsafeBytes { raw -> UInt32 in
            raw.load(as: UInt32.self).bigEndian
        }
        try Self.validateFrameLength(Int(length))
        let body = try Self.readExactFromSocket(fd: socketFD, count: Int(length), deadline: deadline)
        let object = try JSONSerialization.jsonObject(with: body)
        guard let dictionary = object as? [String: Any] else {
            throw CAPTRuntimeClientError.malformedResponse("top-level JSON is not an object")
        }
        return dictionary
    }

    static func waitForSocket(fd: Int32, events: Int16, deadline: TimeInterval) throws {
        while true {
            let remaining = deadline - ProcessInfo.processInfo.systemUptime
            if remaining <= 0 {
                throw CAPTRuntimeClientError.socketFailure(
                    "CAPT socket I/O deadline expired; response outcome indeterminate"
                )
            }
            var entry = pollfd(fd: fd, events: events, revents: 0)
            let milliseconds = Int32(min(1000, max(1, Int(remaining * 1000))))
            let rc = Darwin.poll(&entry, 1, milliseconds)
            if rc > 0 { return }
            if rc < 0 && errno == EINTR { continue }
            if rc < 0 {
                throw CAPTRuntimeClientError.socketFailure(
                    "CAPT socket poll failed: \(String(cString: strerror(errno)))"
                )
            }
        }
    }

    static func readExactFromSocket(fd: Int32, count: Int, deadline: TimeInterval) throws -> Data {
        var data = Data(count: count)
        var receivedTotal = 0
        try data.withUnsafeMutableBytes { rawBuffer in
            guard let baseAddress = rawBuffer.baseAddress else { return }
            while receivedTotal < count {
                try waitForSocket(fd: fd, events: Int16(POLLIN), deadline: deadline)
                let received = Darwin.recv(
                    fd, baseAddress.advanced(by: receivedTotal),
                    count - receivedTotal, 0
                )
                if received < 0 && errno == EINTR { continue }
                if received < 0 && (errno == EWOULDBLOCK || errno == EAGAIN) {
                    continue // poll again, but never extend the absolute deadline
                }
                if received <= 0 {
                    throw CAPTRuntimeClientError.socketFailure(
                        "CAPT socket closed mid-frame; response outcome indeterminate"
                    )
                }
                receivedTotal += received
            }
        }
        return data
    }

    static func configureIOTimeout(fd: Int32) throws {
        var timeout = timeval(tv_sec: 1, tv_usec: 0)
        for option in [SO_RCVTIMEO, SO_SNDTIMEO] {
            let rc = Darwin.setsockopt(
                fd, SOL_SOCKET, option, &timeout,
                socklen_t(MemoryLayout<timeval>.size)
            )
            guard rc == 0 else {
                throw CAPTRuntimeClientError.socketFailure("Unable to set CAPT socket I/O timeout")
            }
        }
    }

    static func configureNoSigPipe(fd: Int32) throws {
        var enabled: Int32 = 1
        let result = Darwin.setsockopt(
            fd,
            SOL_SOCKET,
            SO_NOSIGPIPE,
            &enabled,
            socklen_t(MemoryLayout<Int32>.size)
        )
        guard result == 0 else {
            throw CAPTRuntimeClientError.socketFailure(
                "Unable to suppress SIGPIPE on CAPT socket: \(String(cString: strerror(errno)))"
            )
        }
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
        do {
            try configureNoSigPipe(fd: fd)
            try configureIOTimeout(fd: fd)
        } catch {
            Darwin.close(fd)
            throw error
        }
        let originalFlags = Darwin.fcntl(fd, F_GETFL)
        guard originalFlags >= 0 && Darwin.fcntl(fd, F_SETFL, originalFlags | O_NONBLOCK) == 0 else {
            Darwin.close(fd)
            throw CAPTRuntimeClientError.socketFailure("Unable to bound CAPT socket connection time")
        }
        do {
            let result = withUnsafePointer(to: &address) { pointer in
                pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { socketAddress in
                    Darwin.connect(fd, socketAddress, socklen_t(MemoryLayout<sockaddr_un>.size))
                }
            }
            if result < 0 {
                guard errno == EINPROGRESS || errno == EWOULDBLOCK else {
                    throw CAPTRuntimeClientError.socketFailure(
                        "Unable to connect to CAPT runtime at \(path): \(String(cString: strerror(errno)))"
                    )
                }
                try waitForSocket(
                    fd: fd, events: Int16(POLLOUT),
                    deadline: ProcessInfo.processInfo.systemUptime + socketIODeadlineSeconds
                )
                var socketError: Int32 = 0
                var socketErrorLength = socklen_t(MemoryLayout<Int32>.size)
                guard Darwin.getsockopt(fd, SOL_SOCKET, SO_ERROR, &socketError, &socketErrorLength) == 0,
                      socketError == 0 else {
                    throw CAPTRuntimeClientError.socketFailure(
                        "CAPT socket connect failed after readiness check"
                    )
                }
            }
            guard Darwin.fcntl(fd, F_SETFL, originalFlags) == 0 else {
                throw CAPTRuntimeClientError.socketFailure("Unable to restore CAPT socket mode")
            }
            return fd
        } catch {
            Darwin.close(fd)
            throw error
        }
    }
}
