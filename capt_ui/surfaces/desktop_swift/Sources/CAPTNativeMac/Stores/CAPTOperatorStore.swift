import Foundation
import Combine
import CAPTCoreDesktop

@MainActor
final class CAPTOperatorStore: ObservableObject {
    @Published var connectionState: CAPTRuntimeConnectionState = .disconnected
    @Published var messages: [CAPTChatMessage] = [
        CAPTChatMessage(
            role: .system,
            text: "CAPT native surface ready. Connect to RuntimeService to begin."
        )
    ]
    @Published var pendingApproval: CAPTPendingApproval?
    @Published var provider = "ollama"
    @Published var model = "qwen3.5-defiant-fable:latest"
    @Published var targetRoot = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("CAPT_core", isDirectory: true).path
    @Published var runtimeIdentity = "Not connected"
    @Published var taskState = "—"
    @Published var isBusy = false
    @Published var lastError: String?
    @Published var missions: [CAPTMissionSummary] = []
    @Published var evidenceItems: [CAPTEvidenceSummary] = []
    @Published var recentEvents: [CAPTEventSummary] = []

    private let runtime: CAPTBackgroundRuntime

    init(runtime: CAPTBackgroundRuntime = CAPTBackgroundRuntime()) {
        self.runtime = runtime
    }

    var connectionLabel: String {
        switch connectionState {
        case .disconnected: return "Disconnected"
        case .connecting: return "Connecting…"
        case .connected: return "Connected"
        case .failed(let message): return "Failed: \(message)"
        }
    }

    func connect() {
        guard connectionState != .connecting else { return }
        connectionState = .connecting
        isBusy = true
        lastError = nil
        Task {
            do {
                let response = try await runtime.connect()
                let identity = response["result"] as? [String: Any] ?? response
                let version = identity["runtimeVersion"] as? String ?? "CAPT"
                let integrity = identity["integrity"] as? String ?? "unknown"
                runtimeIdentity = "\(version) · integrity \(integrity)"
                connectionState = .connected
                refreshHistory()
            } catch {
                let message = error.localizedDescription
                lastError = message
                connectionState = .failed(message)
            }
            isBusy = false
        }
    }

    func disconnect() {
        Task { await runtime.disconnect() }
        connectionState = .disconnected
        runtimeIdentity = "Not connected"
        pendingApproval = nil
    }

    func submitPrompt(_ text: String) {
        let objective = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !objective.isEmpty, connectionState == .connected else { return }
        guard pendingApproval == nil, !isBusy else { return }

        messages.append(CAPTChatMessage(role: .user, text: objective))
        isBusy = true
        lastError = nil
        let selectedProvider = provider
        let selectedModel = model
        let root = targetRoot

        Task {
            do {
                let pending = try await runtime.requestApproval(
                    objective: objective,
                    targetRoot: root,
                    provider: selectedProvider,
                    model: selectedModel
                )
                pendingApproval = pending
                taskState = "approval_required"
                messages.append(CAPTChatMessage(
                    role: .system,
                    text: "CAPT prepared a bound execution. Review and approve before dispatch.",
                    authorityState: "approval_required"
                ))
                refreshHistory()
            } catch {
                handle(error)
            }
            isBusy = false
        }
    }

    func approvePending() {
        guard let pending = pendingApproval, !isBusy else { return }
        isBusy = true
        lastError = nil
        Task {
            do {
                let result = try await runtime.approveAndRun(pending)
                pendingApproval = nil
                taskState = result.taskState
                messages.append(CAPTChatMessage(
                    role: .assistant,
                    text: result.text,
                    authorityState: result.taskState
                ))
                refreshHistory()
            } catch {
                handle(error)
            }
            isBusy = false
        }
    }

    func denyPending() {
        guard let pending = pendingApproval, !isBusy else { return }
        isBusy = true
        lastError = nil
        Task {
            do {
                try await runtime.deny(pending)
                pendingApproval = nil
                taskState = "denied"
                messages.append(CAPTChatMessage(
                    role: .system,
                    text: "Execution denied. No model dispatch was authorized.",
                    authorityState: "denied"
                ))
                refreshHistory()
            } catch {
                handle(error)
            }
            isBusy = false
        }
    }

    func refreshIdentity() {
        guard connectionState == .connected, !isBusy else { return }
        Task {
            do {
                let response = try await runtime.identity()
                let identity = response["result"] as? [String: Any] ?? response
                let version = identity["runtimeVersion"] as? String ?? "CAPT"
                let integrity = identity["integrity"] as? String ?? "unknown"
                runtimeIdentity = "\(version) · integrity \(integrity)"
            } catch {
                handle(error)
            }
        }
    }

    func refreshHistory() {
        guard connectionState == .connected else { return }
        Task {
            do {
                let snapshot = try await runtime.historySnapshot()
                missions = snapshot.missions
                evidenceItems = snapshot.evidence
                recentEvents = snapshot.events
            } catch {
                lastError = error.localizedDescription
            }
        }
    }

    func refreshAll() {
        refreshIdentity()
        refreshHistory()
    }

    private func handle(_ error: Error) {
        let message = error.localizedDescription
        lastError = message
        messages.append(CAPTChatMessage(
            role: .system,
            text: message,
            authorityState: "error"
        ))
    }
}
