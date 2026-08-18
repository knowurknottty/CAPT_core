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
    @Published var approvals: [CAPTApprovalSummary] = []
    @Published var recentEvents: [CAPTEventSummary] = []
    @Published var providers: [CAPTProviderSnapshot] = []
    @Published var modelSnapshot: CAPTModelSelectionSnapshot?
    @Published var verbosity = "normal"
    @Published var memorySnapshot: CAPTMemoryRuntimeSnapshot?
    @Published var checkpointSnapshot: CAPTCheckpointSnapshot?
    @Published var runtimeControlMessage = ""
    @Published var sessions: [CAPTNativeSession] = []
    @Published var activeSessionID: UUID?

    private let runtime: CAPTBackgroundRuntime
    private let sessionStore: CAPTEncryptedSessionStore

    init(
        runtime: CAPTBackgroundRuntime = CAPTBackgroundRuntime(),
        sessionStore: CAPTEncryptedSessionStore = CAPTEncryptedSessionStore()
    ) {
        self.runtime = runtime
        self.sessionStore = sessionStore
        do {
            sessions = try sessionStore.load().sorted { $0.updatedAt > $1.updatedAt }
            if let first = sessions.first { activateSession(first.id) }
        } catch {
            lastError = "Native session cache: " + error.localizedDescription
        }
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
                refreshAll()
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

        ensureActiveSession(titleFrom: objective)
        messages.append(CAPTChatMessage(role: .user, text: objective))
        persistActiveSession()
        isBusy = true
        lastError = nil
        let selectedProvider = provider
        let selectedModel = model
        let root = targetRoot
        let missionID = activeMissionID

        Task {
            do {
                let pending = try await runtime.requestApproval(
                    objective: objective,
                    targetRoot: root,
                    provider: selectedProvider,
                    model: selectedModel,
                    missionID: missionID
                )
                pendingApproval = pending
                bindActiveSession(to: pending.missionID)
                taskState = "approval_required"
                messages.append(CAPTChatMessage(
                    role: .system,
                    text: "CAPT prepared a bound execution. Review and approve before dispatch.",
                    authorityState: "approval_required"
                ))
                persistActiveSession()
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
                persistActiveSession()
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
                persistActiveSession()
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
                approvals = snapshot.approvals
                recentEvents = snapshot.events
            } catch {
                lastError = error.localizedDescription
            }
        }
    }

    func refreshOperatorState() {
        Task {
            do {
                let snapshot = try await runtime.operatorSnapshot()
                providers = snapshot.providers
                modelSnapshot = snapshot.models
                verbosity = snapshot.verbosity
                if activeSessionID == nil {
                    if let selected = snapshot.providers.first(where: { $0.selected }) {
                        provider = selected.id
                    } else if let selected = snapshot.models.defaultSelection {
                        provider = selected.provider
                    }
                    if !snapshot.models.active.isEmpty { model = snapshot.models.active }
                }
            } catch { lastError = error.localizedDescription }
        }
    }

    func refreshMemory() {
        guard connectionState == .connected else { return }
        Task {
            do { memorySnapshot = try await runtime.memorySnapshot() }
            catch { lastError = error.localizedDescription }
        }
    }

    func refreshAll() {
        refreshIdentity()
        refreshHistory()
        refreshOperatorState()
        refreshMemory()
    }



    var pendingApprovals: [CAPTApprovalSummary] {
        approvals.filter { $0.state == "requested" && $0.decision == nil }
    }

    func decideQueuedApproval(_ item: CAPTApprovalSummary, decision: String) {
        guard !isBusy, item.state == "requested", item.decision == nil else { return }
        isBusy = true
        Task {
            do {
                _ = try await runtime.decideApproval(requestID: item.id, decision: decision)
                runtimeControlMessage = "Approval \(decision) recorded"
                refreshHistory()
            } catch { handle(error) }
            isBusy = false
        }
    }

    func activateProvider(_ providerID: String) {
        guard !isBusy else { return }
        isBusy = true
        Task {
            do {
                providers = try await runtime.activateProvider(providerID)
                provider = providerID
                let snapshot = try await runtime.operatorSnapshot()
                modelSnapshot = snapshot.models
                if let first = providers.first(where: { $0.id == providerID })?.models.first {
                    model = first
                }
                persistActiveSession()
            } catch { handle(error) }
            isBusy = false
        }
    }

    func testProvider(_ providerID: String) {
        guard !isBusy else { return }
        isBusy = true
        Task {
            do { providers = try await runtime.testProvider(providerID) }
            catch { handle(error) }
            isBusy = false
        }
    }

    func setProviderKeyReference(providerID: String, reference: String) {
        guard !isBusy else { return }
        isBusy = true
        Task {
            do { providers = try await runtime.setProviderKeyReference(providerID: providerID, reference: reference) }
            catch { handle(error) }
            isBusy = false
        }
    }

    func setDefaultModel(_ modelID: String) {
        guard !isBusy else { return }
        let providerID = provider
        isBusy = true
        Task {
            do {
                modelSnapshot = try await runtime.setDefaultModel(providerID: providerID, modelID: modelID)
                model = modelID
                persistActiveSession()
            } catch { handle(error) }
            isBusy = false
        }
    }

    func setVerbosity(_ value: String) {
        Task {
            do { verbosity = try await runtime.setVerbosity(value) }
            catch { handle(error) }
        }
    }

    func createCheckpoint() {
        guard connectionState == .connected, !isBusy else { return }
        isBusy = true
        Task {
            do {
                checkpointSnapshot = try await runtime.checkpoint()
                runtimeControlMessage = "Checkpoint committed"
            } catch { handle(error) }
            isBusy = false
        }
    }

    func resumeRuntime() {
        guard connectionState == .connected, !isBusy else { return }
        isBusy = true
        Task {
            do {
                _ = try await runtime.resume()
                runtimeControlMessage = "Runtime resume accepted"
                refreshAll()
            } catch { handle(error) }
            isBusy = false
        }
    }

    var activeMissionID: String? {
        guard let id = activeSessionID,
              let session = sessions.first(where: { $0.id == id }) else { return nil }
        return session.missionID
    }

    var activeSessionTitle: String {
        guard let id = activeSessionID,
              let session = sessions.first(where: { $0.id == id }) else { return "CAPT Chat" }
        return session.title
    }

    func newChat() {
        guard pendingApproval == nil, !isBusy else { return }
        let welcome = CAPTChatMessage(role: .system, text: "New governed CAPT chat ready.")
        let session = CAPTNativeSession(
            title: "New Chat", messages: [welcome], provider: provider,
            model: model, targetRoot: targetRoot
        )
        sessions.insert(session, at: 0)
        activeSessionID = session.id
        messages = session.messages
        taskState = "—"
        persistActiveSession()
    }

    func activateSession(_ id: UUID) {
        guard pendingApproval == nil, !isBusy || activeSessionID == nil else { return }
        guard let session = sessions.first(where: { $0.id == id }) else { return }
        activeSessionID = id
        messages = session.messages
        provider = session.provider
        model = session.model
        targetRoot = session.targetRoot
        pendingApproval = session.pendingApproval
        taskState = pendingApproval == nil ? "—" : "approval_required"
    }

    private func ensureActiveSession(titleFrom objective: String) {
        if activeSessionID == nil {
            let title = String(objective.prefix(72))
            let session = CAPTNativeSession(
                title: title, messages: messages, provider: provider,
                model: model, targetRoot: targetRoot
            )
            sessions.insert(session, at: 0)
            activeSessionID = session.id
        } else if let id = activeSessionID,
                  let index = sessions.firstIndex(where: { $0.id == id }),
                  sessions[index].title == "New Chat" {
            sessions[index].title = String(objective.prefix(72))
        }
    }

    private func bindActiveSession(to missionID: String) {
        guard let id = activeSessionID,
              let index = sessions.firstIndex(where: { $0.id == id }) else { return }
        if sessions[index].missionID == nil { sessions[index].missionID = missionID }
    }

    private func persistActiveSession() {
        guard let id = activeSessionID,
              let index = sessions.firstIndex(where: { $0.id == id }) else { return }
        sessions[index].messages = messages
        sessions[index].provider = provider
        sessions[index].model = model
        sessions[index].targetRoot = targetRoot
        sessions[index].pendingApproval = pendingApproval
        sessions[index].updatedAt = Date()
        let current = sessions.remove(at: index)
        sessions.insert(current, at: 0)
        do { try sessionStore.save(sessions) }
        catch { lastError = "Native session cache: " + error.localizedDescription }
    }

    private func handle(_ error: Error) {
        let message = error.localizedDescription
        lastError = message
        messages.append(CAPTChatMessage(
            role: .system,
            text: message,
            authorityState: "error"
        ))
        persistActiveSession()
    }
}
