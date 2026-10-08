import Foundation

/// Safe generic *read* bridge: only runtime-advertised query operations can run.
/// No command envelope, capability mint, or implicit HumanApproval is constructed.
public final class CAPTRuntimeQueryExplorer {
    private let client: CAPTRuntimeCommanding
    public init(client: CAPTRuntimeCommanding) { self.client = client }

    public func perform(operation: String, payloadJSON: String) throws -> String {
        let raw = payloadJSON.trimmingCharacters(in: .whitespacesAndNewlines)
        guard raw.utf8.count <= 16_384 else {
            throw CAPTRuntimeClientError.malformedResponse("Query payload exceeds 16 KiB")
        }
        let payload: [String: Any]
        if raw.isEmpty {
            payload = [:]
        } else {
            let data = Data(raw.utf8)
            guard let object = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                throw CAPTRuntimeClientError.malformedResponse("Query payload must be a JSON object")
            }
            payload = object
        }
        guard !payload.keys.contains("op"), !payload.keys.contains("token"),
              !payload.keys.contains("command") else {
            throw CAPTRuntimeClientError.malformedResponse(
                "Query payload cannot override runtime authentication or operation"
            )
        }
        let contract = try client.query(op: "capabilities", payload: [:])
        guard contract["ok"] as? Bool == true,
              let result = contract["result"] as? [String: Any],
              let queries = result["queryOperations"] as? [String],
              queries.contains(operation), operation != "command" else {
            throw CAPTRuntimeClientError.malformedResponse(
                "Operation not advertised as read-only by RuntimeService: " + operation
            )
        }
        let response = try client.query(op: operation, payload: payload)
        guard response["ok"] as? Bool == true else {
            throw CAPTRuntimeClientError.malformedResponse(
                "Runtime query rejected: " + String(describing: response["error"] ?? "unknown")
            )
        }
        let data = try JSONSerialization.data(
            withJSONObject: response, options: [.prettyPrinted, .sortedKeys]
        )
        // Preview only; authoritative content remains in the runtime.
        let prefix = data.prefix(64_000)
        return String(decoding: prefix, as: UTF8.self) +
            (data.count > prefix.count ? "\n… [preview truncated at 64 KiB]" : "")
    }
}
