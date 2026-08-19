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
    @Published var driverRuns: [CAPTDriverRunSummary] = []
    @Published var recentEvents: [CAPTEventSummary] = []
    @Published var providers: [CAPTProviderSnapshot] = []
    @Published var modelSnapshot: CAPTModelSelectionSnapshot?
    @Published var verbosity = "normal"
    @Published var memorySnapshot: CAPTMemoryRuntimeSnapshot?
    @Published var checkpointSnapshot: CAPTCheckpointSnapshot?
    @Published var runtimeControlMessage = ""
    @Published var runtimeCapabilities: CAPTRuntimeCapabilitiesSnapshot?
    @Published var claimReview: CAPTClaimReviewSnapshot?
    @Published var reviewedClaimID: String?
    @Published var sessions: [CAPTNativeSession] = []
    @Published var activeSessionID: UUID?
    @Published var selectedSection: CAPTSidebarSection = .chat

    private let runtime: CAPTBackgroundRuntime
    private let sessionStore: CAPTEncryptedSessionStore

    init(
        runtime: CAPTBackgroundRuntime = CAPTBackgroundRuntime(),
        sessionStore: CAPTEncryptedSessionStore = CAPTEncryptedSessionStore()
    ) {
        self.runtime = runtime
        self.sessionStore = sessionStore
        restoreSessionsAsync()
    }

    private func restoreSessionsAsync() {
        let store = sessionStore
        Task {
            let result = await Task.detached { () -> Result<[CAPTNativeSession], Error> in
                do { return .success(try store.load()) }
                catch { return .failure(error) }
            }.value
            switch result {
            case .success(let restored):
                sessions = restored.sorted { $0.updatedAt > $1.updatedAt }
                if activeSessionID == nil, let first = sessions.first { activateSession(first.id) }
            case .failure(let error):
                lastError = "Native session cache: " + error.localizedDescription
            }
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
                let identity = try await runtime.connect()
                runtimeIdentity = "\(identity.runtimeVersion) · integrity \(identity.integrity)"
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
        guard let originSessionID = activeSessionID else { return }
        messages.append(CAPTChatMessage(role: .user, text: objective))
        persistActiveSession()
        isBusy = true
        lastError = nil
        let selectedProvider = provider
        let selectedModel = model
        let root = targetRoot
        let missionID = activeMissionID

        Task {
            defer { isBusy = false }
            do {
                let pending = try await runtime.requestApproval(
                    objective: objective,
                    targetRoot: root,
                    provider: selectedProvider,
                    model: selectedModel,
                    missionID: missionID
                )
                updateSession(
                    originSessionID, missionID: pending.missionID,
                    append: CAPTChatMessage(
                        role: .system,
                        text: "CAPT prepared a bound execution. Review and approve before dispatch.",
                        authorityState: "approval_required"
                    ),
                    pendingApproval: .set(pending), taskState: "approval_required"
                )
                refreshHistory()
            } catch {
                handle(error, sessionID: originSessionID)
            }
        }
    }

    func approvePending() {
        guard let pending = pendingApproval, !isBusy, let originSessionID = activeSessionID else { return }
        isBusy = true
        lastError = nil
        Task {
            defer { isBusy = false }
            do {
                let result = try await runtime.approveAndRun(pending)
                updateSession(
                    originSessionID,
                    append: CAPTChatMessage(
                        role: .assistant, text: result.text, authorityState: result.taskState
                    ),
                    pendingApproval: .clear, taskState: result.taskState
                )
                refreshHistory()
            } catch {
                if CAPTApprovalPresentation.isExpiredError(error) {
                    updateSession(
                        originSessionID,
                        append: CAPTChatMessage(
                            role: .system,
                            text: CAPTApprovalPresentation.expiredMessage,
                            authorityState: "approval_expired"
                        ),
                        pendingApproval: .clear, taskState: "approval_expired"
                    )
                }
                handle(error, sessionID: originSessionID, appendMessage: !CAPTApprovalPresentation.isExpiredError(error))
            }
        }
    }

    func denyPending() {
        guard let pending = pendingApproval, !isBusy, let originSessionID = activeSessionID else { return }
        isBusy = true
        lastError = nil
        Task {
            defer { isBusy = false }
            do {
                try await runtime.deny(pending)
                updateSession(
                    originSessionID,
                    append: CAPTChatMessage(
                        role: .system,
                        text: "Execution denied. No model dispatch was authorized.",
                        authorityState: "denied"
                    ),
                    pendingApproval: .clear, taskState: "denied"
                )
                refreshHistory()
            } catch {
                if CAPTApprovalPresentation.isExpiredError(error) {
                    updateSession(
                        originSessionID,
                        append: CAPTChatMessage(
                            role: .system,
                            text: CAPTApprovalPresentation.expiredMessage,
                            authorityState: "approval_expired"
                        ),
                        pendingApproval: .clear, taskState: "approval_expired"
                    )
                }
                handle(error, sessionID: originSessionID, appendMessage: !CAPTApprovalPresentation.isExpiredError(error))
            }
        }
    }

    func refreshIdentity() {
        guard connectionState == .connected, !isBusy else { return }
        Task {
            do {
                let identity = try await runtime.identity()
                runtimeIdentity = "\(identity.runtimeVersion) · integrity \(identity.integrity)"
            } catch {
                handleGlobal(error)
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
                driverRuns = snapshot.driverRuns
                recentEvents = snapshot.events
                reconcileCachedApprovals(authoritative: snapshot.approvals)
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

    func refreshCapabilities() {
        guard connectionState == .connected else { return }
        Task {
            do { runtimeCapabilities = try await runtime.capabilitiesSnapshot() }
            catch { lastError = error.localizedDescription }
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
        refreshCapabilities()
    }



    var pendingApprovals: [CAPTApprovalSummary] {
        approvals.filter { $0.state == "requested" && $0.decision == nil }
    }

    func decideQueuedApproval(_ item: CAPTApprovalSummary, decision: String) {
        guard !isBusy, item.state == "requested", item.decision == nil else { return }
        isBusy = true
        Task {
            defer { isBusy = false }
            do {
                try await runtime.decideApproval(requestID: item.id, decision: decision)
                runtimeControlMessage = "Approval \(decision) recorded"
                refreshHistory()
            } catch { handleGlobal(error) }
        }
    }

    func activateProvider(_ providerID: String) {
        guard !isBusy else { return }
        let originSessionID = activeSessionID
        isBusy = true
        Task {
            defer { isBusy = false }
            do {
                providers = try await runtime.activateProvider(providerID)
                let snapshot = try await runtime.operatorSnapshot()
                modelSnapshot = snapshot.models
                let selectedModel = providers.first(where: { $0.id == providerID })?.models.first ?? model
                if let originSessionID {
                    updateSession(originSessionID, provider: providerID, model: selectedModel)
                } else {
                    provider = providerID
                    model = selectedModel
                }
            } catch { handleGlobal(error) }
        }
    }

    func testProvider(_ providerID: String) {
        guard !isBusy else { return }
        isBusy = true
        Task {
            defer { isBusy = false }
            do { providers = try await runtime.testProvider(providerID) }
            catch { handleGlobal(error) }
        }
    }

    func setProviderKeyReference(providerID: String, reference: String) {
        guard !isBusy else { return }
        isBusy = true
        Task {
            defer { isBusy = false }
            do { providers = try await runtime.setProviderKeyReference(providerID: providerID, reference: reference) }
            catch { handleGlobal(error) }
        }
    }

    func setDefaultModel(_ modelID: String) {
        guard !isBusy else { return }
        let providerID = provider
        let originSessionID = activeSessionID
        isBusy = true
        Task {
            defer { isBusy = false }
            do {
                modelSnapshot = try await runtime.setDefaultModel(providerID: providerID, modelID: modelID)
                if let originSessionID {
                    updateSession(originSessionID, model: modelID)
                } else {
                    model = modelID
                }
            } catch { handleGlobal(error) }
        }
    }

    func setVerbosity(_ value: String) {
        Task {
            do { verbosity = try await runtime.setVerbosity(value) }
            catch { handleGlobal(error) }
        }
    }

    func createCheckpoint() {
        guard connectionState == .connected, !isBusy else { return }
        isBusy = true
        Task {
            defer { isBusy = false }
            do {
                checkpointSnapshot = try await runtime.checkpoint()
                runtimeControlMessage = "Checkpoint committed"
            } catch { handleGlobal(error) }
        }
    }

    func resumeRuntime() {
        guard connectionState == .connected, !isBusy else { return }
        isBusy = true
        Task {
            defer { isBusy = false }
            do {
                try await runtime.resume()
                runtimeControlMessage = "Runtime resume accepted"
                refreshAll()
            } catch { handleGlobal(error) }
        }
    }

    func cancelTask(_ taskID: String) {
        guard runtimeCapabilities?.supportsCommand("cancel_task") == true, !isBusy else { return }
        isBusy = true
        Task {
            defer { isBusy = false }
            do {
                try await runtime.cancelTask(taskID)
                runtimeControlMessage = "Task cancelled: " + taskID
                refreshHistory()
            } catch { handleGlobal(error) }
        }
    }

    func cancelDriverRun(_ driverRunID: String) {
        guard runtimeCapabilities?.supportsCommand("cancel_driver_run") == true, !isBusy else { return }
        isBusy = true
        Task {
            defer { isBusy = false }
            do {
                try await runtime.cancelDriverRun(driverRunID)
                runtimeControlMessage = "DriverRun cancelled: " + driverRunID
                refreshHistory()
            } catch { handleGlobal(error) }
        }
    }

    func updateMemoryPolicy(
        retrieval: Int, compression: Int, checkpoint: Int,
        consolidation: Int, hardStop: Int, modelSafe: Int
    ) {
        guard runtimeCapabilities?.supportsCommand("update_memory_trigger_policy") == true, !isBusy else { return }
        isBusy = true
        Task {
            defer { isBusy = false }
            do {
                memorySnapshot = try await runtime.updateMemoryPolicy(
                    retrieval: retrieval, compression: compression, checkpoint: checkpoint,
                    consolidation: consolidation, hardStop: hardStop, modelSafe: modelSafe
                )
                runtimeControlMessage = "Memory trigger policy accepted by RuntimeService"
            } catch { handleGlobal(error) }
        }
    }

    func reviewClaim(_ item: CAPTEvidenceSummary) {
        guard runtimeCapabilities?.supportsQuery("claimguard") == true,
              runtimeCapabilities?.supportsQuery("verification") == true else { return }
        Task {
            do {
                claimReview = try await runtime.claimReview(claimID: item.id, statement: item.statement)
                reviewedClaimID = item.id
            } catch { handleGlobal(error) }
        }
    }

    func shutdownRuntime() {
        guard runtimeCapabilities?.supportsCommand("shutdown") == true, !isBusy else { return }
        isBusy = true
        Task {
            defer { isBusy = false }
            do {
                try await runtime.shutdown()
                connectionState = .disconnected
                runtimeIdentity = "Not connected"
                runtimeControlMessage = "Runtime shutdown accepted. Connect will bootstrap it again."
            } catch { handleGlobal(error) }
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
        selectedSection = .chat
        persistActiveSession()
        let welcome = CAPTChatMessage(role: .system, text: "New governed CAPT chat ready.")
        let session = CAPTNativeSession(
            title: "New Chat", messages: [welcome], provider: provider,
            model: model, targetRoot: targetRoot, taskState: "—"
        )
        sessions.insert(session, at: 0)
        activeSessionID = session.id
        loadSessionIntoPresentation(session)
        lastError = nil
        persistActiveSession()
    }

    func activateSession(_ id: UUID) {
        guard let session = sessions.first(where: { $0.id == id }) else { return }
        selectedSection = .chat
        if activeSessionID != id { persistActiveSession() }
        activeSessionID = id
        loadSessionIntoPresentation(session)
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

    private func reconcileCachedApprovals(authoritative approvals: [CAPTApprovalSummary]) {
        var changed = false
        for index in sessions.indices {
            guard let cached = sessions[index].pendingApproval else { continue }
            if !CAPTApprovalPresentation.isActionable(cached, authoritative: approvals) {
                sessions[index].pendingApproval = nil
                if sessions[index].taskState == nil || sessions[index].taskState == "approval_required" {
                    sessions[index].taskState = "approval_unavailable"
                }
                sessions[index].updatedAt = Date()
                changed = true
            }
        }
        guard changed else { return }
        saveSessions()
        if let id = activeSessionID, let active = sessions.first(where: { $0.id == id }) {
            loadSessionIntoPresentation(active)
        }
    }

    private enum PendingApprovalUpdate {
        case keep
        case set(CAPTPendingApproval)
        case clear
    }

    private func loadSessionIntoPresentation(_ session: CAPTNativeSession) {
        messages = session.messages
        provider = session.provider
        model = session.model
        targetRoot = session.targetRoot
        pendingApproval = session.pendingApproval
        taskState = session.taskState ?? (session.pendingApproval == nil ? "—" : "approval_required")
    }

    private func updateSession(
        _ id: UUID,
        missionID: String? = nil,
        append message: CAPTChatMessage? = nil,
        pendingApproval update: PendingApprovalUpdate = .keep,
        taskState newTaskState: String? = nil,
        provider newProvider: String? = nil,
        model newModel: String? = nil
    ) {
        guard let index = sessions.firstIndex(where: { $0.id == id }) else { return }
        if let missionID, sessions[index].missionID == nil { sessions[index].missionID = missionID }
        if let message { sessions[index].messages.append(message) }
        switch update {
        case .keep: break
        case .set(let pending): sessions[index].pendingApproval = pending
        case .clear: sessions[index].pendingApproval = nil
        }
        if let newTaskState { sessions[index].taskState = newTaskState }
        if let newProvider { sessions[index].provider = newProvider }
        if let newModel { sessions[index].model = newModel }
        sessions[index].updatedAt = Date()
        let updated = sessions.remove(at: index)
        sessions.insert(updated, at: 0)
        saveSessions()
        if activeSessionID == id { loadSessionIntoPresentation(updated) }
    }

    private func persistActiveSession() {
        guard let id = activeSessionID,
              let index = sessions.firstIndex(where: { $0.id == id }) else { return }
        sessions[index].messages = messages
        sessions[index].provider = provider
        sessions[index].model = model
        sessions[index].targetRoot = targetRoot
        sessions[index].pendingApproval = pendingApproval
        sessions[index].taskState = taskState
        sessions[index].updatedAt = Date()
        let current = sessions.remove(at: index)
        sessions.insert(current, at: 0)
        saveSessions()
    }

    private func saveSessions() {
        do { try sessionStore.save(sessions) }
        catch { lastError = "Native session cache: " + error.localizedDescription }
    }

    private func handleGlobal(_ error: Error) {
        lastError = error.localizedDescription
    }

    private func handle(_ error: Error, sessionID: UUID? = nil, appendMessage: Bool = true) {
        let message = error.localizedDescription
        lastError = message
        guard appendMessage else { return }
        let chatMessage = CAPTChatMessage(role: .system, text: message, authorityState: "error")
        if let sessionID {
            updateSession(sessionID, append: chatMessage)
        } else {
            messages.append(chatMessage)
            persistActiveSession()
        }
    }

}
