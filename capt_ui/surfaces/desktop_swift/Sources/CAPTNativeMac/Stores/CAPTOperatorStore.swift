import Foundation
import Combine
import CAPTCoreDesktop
import Security

@MainActor
final class CAPTOperatorStore: ObservableObject {
    @Published var connectionState: CAPTRuntimeConnectionState = .disconnected
    @Published var messages: [CAPTChatMessage] = [
        CAPTChatMessage(
            role: .system,
            text: "CAPT native surface ready. Connect to RuntimeService to begin."
        )
    ]
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
    @Published private(set) var chatFlows: [UUID: CAPTChatFlow] = [:]
    @Published var providerCredentialStatus: [String: String] = [:]

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
                chatFlows = Dictionary(uniqueKeysWithValues: sessions.map {
                    ($0.id, CAPTChatFlow(pending: $0.pendingApproval))
                })
                if activeSessionID == nil, let first = sessions.first {
                    activateSession(first.id)
                }
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

    var pendingApproval: CAPTPendingApproval? {
        guard let id = activeSessionID,
              let session = sessions.first(where: { $0.id == id }) else { return nil }
        return session.pendingApproval
    }

    var activeChatFlow: CAPTChatFlow {
        guard let id = activeSessionID else { return CAPTChatFlow() }
        return chatFlows[id] ?? CAPTChatFlow(pending: pendingApproval)
    }

    var isActiveChatBusy: Bool { activeChatFlow.isBusy }

    var canComposeInActiveChat: Bool {
        connectionState == .connected && pendingApproval == nil && activeChatFlow.canCompose
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
        chatFlows = Dictionary(uniqueKeysWithValues: sessions.map {
            ($0.id, CAPTChatFlow(pending: $0.pendingApproval))
        })
    }

    func submitPrompt(_ text: String) {
        let objective = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !objective.isEmpty, connectionState == .connected else { return }

        ensureActiveSession(titleFrom: objective)
        guard let sessionID = activeSessionID,
              pendingApproval(for: sessionID) == nil,
              !chatFlow(for: sessionID).isBusy else { return }

        appendMessage(CAPTChatMessage(role: .user, text: objective), to: sessionID)
        persistSession(sessionID)

        var flow = chatFlow(for: sessionID)
        flow.beginApprovalRequest()
        setChatFlow(flow, for: sessionID)
        lastError = nil

        let selectedProvider = provider
        let selectedModel = model
        let root = targetRoot
        let missionID = session(for: sessionID)?.missionID

        Task {
            do {
                let pending = try await runtime.requestApproval(
                    objective: objective,
                    targetRoot: root,
                    provider: selectedProvider,
                    model: selectedModel,
                    missionID: missionID
                )
                bindSession(sessionID, to: pending.missionID)
                setPendingApproval(pending, for: sessionID)
                appendMessage(CAPTChatMessage(
                    role: .system,
                    text: "CAPT prepared a bound execution. Review and approve before dispatch.",
                    authorityState: "approval_required"
                ), to: sessionID)
                var preparedFlow = chatFlow(for: sessionID)
                preparedFlow.approvalPrepared(pending)
                setChatFlow(preparedFlow, for: sessionID)
                if activeSessionID == sessionID { taskState = "approval_required" }
                persistSession(sessionID)
                refreshHistory()
            } catch {
                var failedFlow = chatFlow(for: sessionID)
                _ = failedFlow.executionFailed(message: error.localizedDescription, pending: nil)
                setChatFlow(failedFlow, for: sessionID)
                handleChat(error, sessionID: sessionID)
            }
        }
    }

    func approvePending() {
        guard let sessionID = activeSessionID,
              let pending = pendingApproval(for: sessionID),
              !chatFlow(for: sessionID).isBusy else { return }

        if pending.isExpired() {
            expireLocalApproval(
                sessionID: sessionID,
                pending: pending,
                detail: "Prompt approval expired before dispatch. Submit the prompt again to mint a fresh approval."
            )
            return
        }

        var flow = chatFlow(for: sessionID)
        flow.beginExecution(pending)
        setChatFlow(flow, for: sessionID)
        lastError = nil

        Task {
            do {
                let result = try await runtime.approveAndRun(pending)
                setPendingApproval(nil, for: sessionID)
                appendMessage(CAPTChatMessage(
                    role: .assistant,
                    text: result.text,
                    authorityState: result.taskState
                ), to: sessionID)
                var completedFlow = chatFlow(for: sessionID)
                completedFlow.executionCompleted(taskState: result.taskState)
                setChatFlow(completedFlow, for: sessionID)
                if activeSessionID == sessionID { taskState = result.taskState }
                persistSession(sessionID)
                refreshHistory()
            } catch {
                let message = error.localizedDescription
                var failedFlow = chatFlow(for: sessionID)
                let disposition = failedFlow.executionFailed(message: message, pending: pending)
                setChatFlow(failedFlow, for: sessionID)

                if disposition.isTerminalForLocalActionCursor {
                    setPendingApproval(nil, for: sessionID)
                }

                switch disposition {
                case .expired:
                    if activeSessionID == sessionID { taskState = "approval_expired" }
                    handleChat(
                        error,
                        sessionID: sessionID,
                        authorityState: "approval_expired",
                        messageOverride: "Prompt approval expired before dispatch. Submit the prompt again to mint a fresh approval. Runtime detail: \(message)"
                    )
                case .consumed:
                    if activeSessionID == sessionID { taskState = "approval_consumed" }
                    handleChat(
                        error,
                        sessionID: sessionID,
                        authorityState: "approval_consumed",
                        messageOverride: "This approval has already been consumed and cannot be reused. Submit the prompt again for a fresh governed execution. Runtime detail: \(message)"
                    )
                case .denied:
                    if activeSessionID == sessionID { taskState = "denied" }
                    handleChat(
                        error,
                        sessionID: sessionID,
                        authorityState: "denied",
                        messageOverride: "This approval is no longer actionable because it was denied. Submit the prompt again if you want a new execution. Runtime detail: \(message)"
                    )
                case .retryable:
                    if activeSessionID == sessionID { taskState = "approval_required" }
                    handleChat(error, sessionID: sessionID)
                }
            }
        }
    }

    func denyPending() {
        guard let sessionID = activeSessionID,
              let pending = pendingApproval(for: sessionID),
              !chatFlow(for: sessionID).isBusy else { return }

        if pending.isExpired() {
            expireLocalApproval(
                sessionID: sessionID,
                pending: pending,
                detail: "Prompt approval expired before it could be denied. The stale local action cursor was cleared."
            )
            return
        }

        var flow = chatFlow(for: sessionID)
        flow.beginExecution(pending)
        setChatFlow(flow, for: sessionID)
        lastError = nil

        Task {
            do {
                try await runtime.deny(pending)
                setPendingApproval(nil, for: sessionID)
                var deniedFlow = chatFlow(for: sessionID)
                deniedFlow.reset()
                setChatFlow(deniedFlow, for: sessionID)
                if activeSessionID == sessionID { taskState = "denied" }
                appendMessage(CAPTChatMessage(
                    role: .system,
                    text: "Execution denied. No model dispatch was authorized.",
                    authorityState: "denied"
                ), to: sessionID)
                persistSession(sessionID)
                refreshHistory()
            } catch {
                let message = error.localizedDescription
                var failedFlow = chatFlow(for: sessionID)
                let disposition = failedFlow.executionFailed(message: message, pending: pending)
                setChatFlow(failedFlow, for: sessionID)
                if disposition.isTerminalForLocalActionCursor {
                    setPendingApproval(nil, for: sessionID)
                }
                handleChat(error, sessionID: sessionID)
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
            try Self.storeProviderSecret(trimmed, account: providerID)
            let reference = "keychain:\(providerID)"
            providers = try await runtime.setProviderKeyReference(
                providerID: providerID,
                reference: reference
            )
            providers = try await runtime.testProvider(providerID)
            if let tested = providers.first(where: { $0.id == providerID }),
               tested.health == "green" {
                let latency = tested.latencyMs.map { " · \($0) ms" } ?? ""
                providerCredentialStatus[providerID] = "Stored securely ✓ · Authenticated ✓\(latency)"
            } else {
                providerCredentialStatus[providerID] = "Stored securely ✓ · provider test did not report green"
            }
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
                    retrieval: retrieval, compression: compression, checkpoint: checkpoint,
                    consolidation: consolidation, hardStop: hardStop, modelSafe: modelSafe
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
                claimReview = try await runtime.claimReview(claimID: item.id, statement: item.statement)
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
        persistActiveSession()
        let welcome = CAPTChatMessage(role: .system, text: "New governed CAPT chat ready.")
        let session = CAPTNativeSession(
            title: "New Chat",
            messages: [welcome],
            provider: provider,
            model: model,
            targetRoot: targetRoot,
            pendingApproval: nil
        )
        sessions.insert(session, at: 0)
        activeSessionID = session.id
        messages = session.messages
        taskState = "—"
        chatFlows[session.id] = CAPTChatFlow()
        lastError = nil
        runtimeControlMessage = ""
        saveSessions()
    }

    func activateSession(_ id: UUID) {
        if activeSessionID != id { persistActiveSession() }
        guard let selected = session(for: id) else { return }
        activeSessionID = id
        messages = selected.messages
        provider = selected.provider
        model = selected.model
        targetRoot = selected.targetRoot
        lastError = nil

        let flow = CAPTChatFlow(pending: selected.pendingApproval)
        setChatFlow(flow, for: id)
        if let pending = selected.pendingApproval, pending.isExpired() {
            expireLocalApproval(
                sessionID: id,
                pending: pending,
                detail: "Prompt approval expired while this chat was inactive. Submit the prompt again to mint a fresh approval."
            )
        } else {
            taskState = selected.pendingApproval == nil ? "—" : "approval_required"
        }
    }

    private func ensureActiveSession(titleFrom objective: String) {
        if activeSessionID == nil {
            let title = String(objective.prefix(72))
            let session = CAPTNativeSession(
                title: title,
                messages: messages,
                provider: provider,
                model: model,
                targetRoot: targetRoot
            )
            sessions.insert(session, at: 0)
            activeSessionID = session.id
            chatFlows[session.id] = CAPTChatFlow()
        } else if let id = activeSessionID,
                  let index = sessions.firstIndex(where: { $0.id == id }),
                  sessions[index].title == "New Chat" {
            sessions[index].title = String(objective.prefix(72))
        }
    }

    private func session(for id: UUID) -> CAPTNativeSession? {
        sessions.first(where: { $0.id == id })
    }

    private func pendingApproval(for id: UUID) -> CAPTPendingApproval? {
        session(for: id)?.pendingApproval
    }

    private func chatFlow(for id: UUID) -> CAPTChatFlow {
        chatFlows[id] ?? CAPTChatFlow(pending: pendingApproval(for: id))
    }

    private func setChatFlow(_ flow: CAPTChatFlow, for id: UUID) {
        chatFlows[id] = flow
    }

    private func setPendingApproval(_ pending: CAPTPendingApproval?, for id: UUID) {
        guard let index = sessions.firstIndex(where: { $0.id == id }) else { return }
        sessions[index].pendingApproval = pending
    }

    private func appendMessage(_ message: CAPTChatMessage, to id: UUID) {
        guard let index = sessions.firstIndex(where: { $0.id == id }) else { return }
        sessions[index].messages.append(message)
        if activeSessionID == id {
            messages = sessions[index].messages
        }
    }

    private func bindSession(_ id: UUID, to missionID: String) {
        guard let index = sessions.firstIndex(where: { $0.id == id }) else { return }
        if sessions[index].missionID == nil { sessions[index].missionID = missionID }
    }

    private func expireLocalApproval(
        sessionID: UUID,
        pending: CAPTPendingApproval,
        detail: String
    ) {
        setPendingApproval(nil, for: sessionID)
        var flow = chatFlow(for: sessionID)
        _ = flow.executionFailed(
            message: "PROMPT_APPROVAL_EXPIRED: \(detail)",
            pending: pending
        )
        setChatFlow(flow, for: sessionID)
        appendMessage(CAPTChatMessage(
            role: .system,
            text: detail,
            authorityState: "approval_expired"
        ), to: sessionID)
        if activeSessionID == sessionID {
            taskState = "approval_expired"
            lastError = detail
        }
        persistSession(sessionID)
    }

    private func persistActiveSession() {
        guard let id = activeSessionID,
              let index = sessions.firstIndex(where: { $0.id == id }) else { return }
        sessions[index].messages = messages
        sessions[index].provider = provider
        sessions[index].model = model
        sessions[index].targetRoot = targetRoot
        persistSession(id)
    }

    private func persistSession(_ id: UUID) {
        guard let index = sessions.firstIndex(where: { $0.id == id }) else { return }
        sessions[index].updatedAt = Date()
        let current = sessions.remove(at: index)
        sessions.insert(current, at: 0)
        saveSessions()
    }

    private func saveSessions() {
        do { try sessionStore.save(sessions) }
        catch { lastError = "Native session cache: " + error.localizedDescription }
    }

    private func handle(_ error: Error) {
        lastError = error.localizedDescription
    }

    private func handleChat(
        _ error: Error,
        sessionID: UUID,
        authorityState: String = "error",
        messageOverride: String? = nil
    ) {
        let message = messageOverride ?? error.localizedDescription
        if activeSessionID == sessionID { lastError = message }
        appendMessage(CAPTChatMessage(
            role: .system,
            text: message,
            authorityState: authorityState
        ), to: sessionID)
        persistSession(sessionID)
    }

    private static func storeProviderSecret(_ secret: String, account: String) throws {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: "capt-provider",
            kSecAttrAccount as String: account,
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
