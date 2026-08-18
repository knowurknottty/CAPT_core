import Foundation
import Combine
import CAPTCoreDesktop
import Security

@MainActor
final class CAPTOperatorStore: ObservableObject {
    private static let startupMessage = CAPTChatMessage(
        role: .system,
        text: "CAPT native surface ready. Connect to RuntimeService to begin."
    )

    @Published var connectionState: CAPTRuntimeConnectionState = .disconnected
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
    @Published var providerCredentialStatus: [String: String] = [:]
    @Published private var chatWorkspace = CAPTNativeChatWorkspace()

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

    var messages: [CAPTChatMessage] {
        chatWorkspace.activeSession?.messages ?? [Self.startupMessage]
    }

    var sessions: [CAPTNativeSession] {
        chatWorkspace.sessions
    }

    var activeSessionID: UUID? {
        chatWorkspace.activeSessionID
    }

    var pendingApproval: CAPTPendingApproval? {
        chatWorkspace.activePendingApproval
    }

    var activeChatFlow: CAPTChatFlow {
        chatWorkspace.activeFlow
    }

    var isActiveChatBusy: Bool {
        activeChatFlow.isBusy
    }

    var canComposeInActiveChat: Bool {
        connectionState == .connected &&
            pendingApproval == nil &&
            activeChatFlow.canCompose
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
                var workspace = chatWorkspace
                workspace.mergeRestoredSessions(restored)
                if workspace.activeSessionID == nil, let first = workspace.sessions.first {
                    _ = workspace.activate(first.id)
                }
                chatWorkspace = workspace
                syncSelectionFromActiveSession()
                updateTaskStateFromActiveFlow()
                saveSessions()
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
    }

    func submitPrompt(_ text: String) {
        guard connectionState == .connected else { return }

        if activeSessionID == nil {
            _ = mutateWorkspace {
                $0.newChat(provider: provider, model: model, targetRoot: targetRoot)
            }
        }

        guard let sessionID = mutateWorkspace({
            $0.beginPrompt(
                text,
                provider: provider,
                model: model,
                targetRoot: targetRoot
            )
        }) else { return }

        saveSessions()
        lastError = nil
        if activeSessionID == sessionID { taskState = "approval_preparing" }

        let selectedProvider = provider
        let selectedModel = model
        let root = targetRoot
        let missionID = chatWorkspace.session(sessionID)?.missionID

        Task {
            do {
                let pending = try await runtime.requestApproval(
                    objective: text.trimmingCharacters(in: .whitespacesAndNewlines),
                    targetRoot: root,
                    provider: selectedProvider,
                    model: selectedModel,
                    missionID: missionID
                )
                mutateWorkspace { $0.receiveApproval(pending, for: sessionID) }
                if activeSessionID == sessionID {
                    updateTaskStateFromActiveFlow()
                    if activeChatFlow.phase == .recoverableFailure {
                        lastError = chatWorkspace.activeSession?.messages.last?.text
                    }
                }
                saveSessions()
                refreshHistory()
            } catch {
                let message = error.localizedDescription
                mutateWorkspace { $0.failApprovalRequest(message: message, for: sessionID) }
                if activeSessionID == sessionID {
                    taskState = "recoverable_failure"
                    lastError = message
                }
                saveSessions()
            }
        }
    }

    func approvePending() {
        guard let sessionID = activeSessionID,
              let localPending = pendingApproval else { return }

        guard let pending = mutateWorkspace({
            $0.beginExecution(for: sessionID)
        }) else {
            if !localPending.isActionable() {
                updateTaskStateFromActiveFlow()
                lastError = chatWorkspace.activeSession?.messages.last?.text
                saveSessions()
            }
            return
        }

        if activeSessionID == sessionID { taskState = "executing" }
        lastError = nil

        Task {
            do {
                let result = try await runtime.approveAndRun(pending)
                mutateWorkspace {
                    $0.completeExecution(
                        text: result.text,
                        taskState: result.taskState,
                        for: sessionID
                    )
                }
                if activeSessionID == sessionID { taskState = result.taskState }
                saveSessions()
                refreshHistory()
            } catch {
                let disposition = mutateWorkspace {
                    $0.failExecution(message: error.localizedDescription, for: sessionID)
                }
                if activeSessionID == sessionID {
                    taskState = Self.taskState(for: disposition)
                    lastError = chatWorkspace.activeSession?.messages.last?.text
                }
                saveSessions()
                refreshHistory()
            }
        }
    }

    func denyPending() {
        guard let sessionID = activeSessionID,
              let localPending = pendingApproval else { return }

        guard let pending = mutateWorkspace({
            $0.beginExecution(for: sessionID)
        }) else {
            if !localPending.isActionable() {
                updateTaskStateFromActiveFlow()
                lastError = chatWorkspace.activeSession?.messages.last?.text
                saveSessions()
            }
            return
        }

        lastError = nil
        Task {
            do {
                try await runtime.deny(pending)
                mutateWorkspace { $0.completeDenial(for: sessionID) }
                if activeSessionID == sessionID { taskState = "denied" }
                saveSessions()
                refreshHistory()
            } catch {
                let disposition = mutateWorkspace {
                    $0.failExecution(message: error.localizedDescription, for: sessionID)
                }
                if activeSessionID == sessionID {
                    taskState = Self.taskState(for: disposition)
                    lastError = chatWorkspace.activeSession?.messages.last?.text
                }
                saveSessions()
                refreshHistory()
            }
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
                driverRuns = snapshot.driverRuns
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
        approvals.filter { $0.isActionable() }
    }

    func decideQueuedApproval(_ item: CAPTApprovalSummary, decision: String) {
        guard !isBusy, item.isActionable() else { return }
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
                persistActiveConfiguration()
            } catch { handle(error) }
            isBusy = false
        }
    }

    func testProvider(_ providerID: String) {
        guard !isBusy else { return }
        isBusy = true
        Task {
            do {
                providers = try await runtime.testProvider(providerID)
                if let tested = providers.first(where: { $0.id == providerID }),
                   tested.health == "green" {
                    let latency = tested.latencyMs.map { " · \($0) ms" } ?? ""
                    providerCredentialStatus[providerID] = "Authenticated ✓\(latency)"
                }
            } catch { handle(error) }
            isBusy = false
        }
    }

    func setProviderKeyReference(providerID: String, reference: String) async -> Bool {
        guard !isBusy else { return false }
        let trimmed = reference.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return false }
        isBusy = true
        defer { isBusy = false }
        lastError = nil
        do {
            providers = try await runtime.setProviderKeyReference(
                providerID: providerID,
                reference: trimmed
            )
            return true
        } catch {
            handle(error)
            return false
        }
    }

    func configureProviderAPIKey(providerID: String, apiKey: String) async -> Bool {
        let trimmed = apiKey.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !isBusy else { return false }
        isBusy = true
        defer { isBusy = false }
        lastError = nil
        providerCredentialStatus[providerID] = "Storing securely…"

        do {
            let location = CAPTProviderSecretConvention.location(providerID: providerID)
            try Self.storeProviderSecret(trimmed, location: location)
            providers = try await runtime.setProviderKeyReference(
                providerID: providerID,
                reference: location.reference
            )
            providers = try await runtime.testProvider(providerID)
            guard let tested = providers.first(where: { $0.id == providerID }),
                  tested.health == "green" else {
                providerCredentialStatus[providerID] = "Stored securely ✓ · Authentication test failed"
                return false
            }
            let latency = tested.latencyMs.map { " · \($0) ms" } ?? ""
            providerCredentialStatus[providerID] = "Stored securely ✓ · Authenticated ✓\(latency)"
            return true
        } catch {
            providerCredentialStatus[providerID] = "Setup failed — key retained for retry"
            handle(error)
            return false
        }
    }

    func setDefaultModel(_ modelID: String) {
        guard !isBusy else { return }
        let providerID = provider
        isBusy = true
        Task {
            do {
                modelSnapshot = try await runtime.setDefaultModel(
                    providerID: providerID,
                    modelID: modelID
                )
                model = modelID
                persistActiveConfiguration()
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

    func cancelTask(_ taskID: String) {
        guard runtimeCapabilities?.supportsCommand("cancel_task") == true, !isBusy else { return }
        isBusy = true
        Task {
            do {
                _ = try await runtime.cancelTask(taskID)
                runtimeControlMessage = "Task cancelled: " + taskID
                refreshHistory()
            } catch { handle(error) }
            isBusy = false
        }
    }

    func cancelDriverRun(_ driverRunID: String) {
        guard runtimeCapabilities?.supportsCommand("cancel_driver_run") == true, !isBusy else { return }
        isBusy = true
        Task {
            do {
                _ = try await runtime.cancelDriverRun(driverRunID)
                runtimeControlMessage = "DriverRun cancelled: " + driverRunID
                refreshHistory()
            } catch { handle(error) }
            isBusy = false
        }
    }

    func updateMemoryPolicy(
        retrieval: Int, compression: Int, checkpoint: Int,
        consolidation: Int, hardStop: Int, modelSafe: Int
    ) {
        guard runtimeCapabilities?.supportsCommand("update_memory_trigger_policy") == true, !isBusy else { return }
        isBusy = true
        Task {
            do {
                memorySnapshot = try await runtime.updateMemoryPolicy(
                    retrieval: retrieval,
                    compression: compression,
                    checkpoint: checkpoint,
                    consolidation: consolidation,
                    hardStop: hardStop,
                    modelSafe: modelSafe
                )
                runtimeControlMessage = "Memory trigger policy accepted by RuntimeService"
            } catch { handle(error) }
            isBusy = false
        }
    }

    func reviewClaim(_ item: CAPTEvidenceSummary) {
        guard runtimeCapabilities?.supportsQuery("claimguard") == true,
              runtimeCapabilities?.supportsQuery("verification") == true else { return }
        Task {
            do {
                claimReview = try await runtime.claimReview(
                    claimID: item.id,
                    statement: item.statement
                )
                reviewedClaimID = item.id
            } catch { handle(error) }
        }
    }

    func shutdownRuntime() {
        guard runtimeCapabilities?.supportsCommand("shutdown") == true, !isBusy else { return }
        isBusy = true
        Task {
            do {
                _ = try await runtime.shutdown()
                connectionState = .disconnected
                runtimeIdentity = "Not connected"
                runtimeControlMessage = "Runtime shutdown accepted. Connect will bootstrap it again."
            } catch { handle(error) }
            isBusy = false
        }
    }

    var activeMissionID: String? {
        chatWorkspace.activeSession?.missionID
    }

    var activeSessionTitle: String {
        chatWorkspace.activeSession?.title ?? "CAPT Chat"
    }

    func newChat() {
        _ = mutateWorkspace {
            $0.newChat(provider: provider, model: model, targetRoot: targetRoot)
        }
        taskState = "—"
        lastError = nil
        runtimeControlMessage = ""
        saveSessions()
    }

    func activateSession(_ id: UUID) {
        guard mutateWorkspace({ $0.activate(id) }) else { return }
        syncSelectionFromActiveSession()
        updateTaskStateFromActiveFlow()
        lastError = activeChatFlow.phase == .recoverableFailure
            ? chatWorkspace.activeSession?.messages.last?.text
            : nil
        saveSessions()
    }

    private func syncSelectionFromActiveSession() {
        guard let session = chatWorkspace.activeSession else { return }
        provider = session.provider
        model = session.model
        targetRoot = session.targetRoot
    }

    private func persistActiveConfiguration() {
        mutateWorkspace {
            $0.updateActiveConfiguration(
                provider: provider,
                model: model,
                targetRoot: targetRoot
            )
        }
        saveSessions()
    }

    private func updateTaskStateFromActiveFlow() {
        if pendingApproval != nil {
            taskState = "approval_required"
            return
        }
        switch activeChatFlow.phase {
        case .idle: taskState = "—"
        case .requestingApproval: taskState = "approval_preparing"
        case .awaitingApproval: taskState = "approval_required"
        case .executing: taskState = "executing"
        case .awaitingVerification: taskState = "awaiting_verification"
        case .recoverableFailure:
            taskState = chatWorkspace.activeSession?.messages.last?.authorityState
                ?? "recoverable_failure"
        }
    }

    @discardableResult
    private func mutateWorkspace<T>(
        _ body: (inout CAPTNativeChatWorkspace) -> T
    ) -> T {
        var copy = chatWorkspace
        let result = body(&copy)
        chatWorkspace = copy
        return result
    }

    private func saveSessions() {
        do { try sessionStore.save(chatWorkspace.sessions) }
        catch { lastError = "Native session cache: " + error.localizedDescription }
    }

    private func handle(_ error: Error) {
        lastError = error.localizedDescription
    }

    private static func taskState(
        for disposition: CAPTApprovalFailureDisposition
    ) -> String {
        switch disposition {
        case .retryable: return "approval_required"
        case .expired: return "approval_expired"
        case .consumed: return "approval_consumed"
        case .denied: return "denied"
        }
    }

    private static func storeProviderSecret(
        _ secret: String,
        location: CAPTProviderSecretLocation
    ) throws {
        guard !location.account.isEmpty else {
            throw NSError(
                domain: "CAPTProviderSecret",
                code: 1,
                userInfo: [NSLocalizedDescriptionKey: "provider identifier is empty"]
            )
        }
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: location.service,
            kSecAttrAccount as String: location.account,
        ]
        let value = Data(secret.utf8)
        let updateStatus = SecItemUpdate(
            query as CFDictionary,
            [kSecValueData as String: value] as CFDictionary
        )
        if updateStatus == errSecSuccess { return }
        guard updateStatus == errSecItemNotFound else {
            throw NSError(domain: NSOSStatusErrorDomain, code: Int(updateStatus))
        }
        var add = query
        add[kSecValueData as String] = value
        add[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        let addStatus = SecItemAdd(add as CFDictionary, nil)
        guard addStatus == errSecSuccess else {
            throw NSError(domain: NSOSStatusErrorDomain, code: Int(addStatus))
        }
    }
}
