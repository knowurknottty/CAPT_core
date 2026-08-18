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
    @Published var labEngines: [CAPTLabEngineSnapshot] = []
    @Published var selectedLabEngineID = "lab.math"
    @Published var selectedLabOperation = "cyclotomic_summary"
    @Published var labInputJSON = "{\"conductor\":5}"
    @Published var labReceipt: CAPTLabRunReceipt?
    @Published var labControlMessage = ""

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

    func refreshLabs() {
        guard connectionState == .connected else { return }
        Task {
            do {
                labEngines = try await runtime.labEngines()
                normalizeLabSelection()
            } catch {
                // A non-Lab CAPT runtime may legitimately omit this additive query.
                labEngines = []
            }
        }
    }

    var selectedLabEngine: CAPTLabEngineSnapshot? {
        labEngines.first { $0.id == selectedLabEngineID }
    }

    var selectedLabOperationSnapshot: CAPTLabOperationSnapshot? {
        selectedLabEngine?.operations.first { $0.name == selectedLabOperation }
    }

    var activeLabMissionSummary: CAPTMissionSummary? {
        guard let missionID = activeMissionID else { return nil }
        return missions.first { $0.id == missionID }
    }

    var activeLabTaskID: String? { activeLabMissionSummary?.taskID }

    func selectLabEngine(_ engineID: String) {
        selectedLabEngineID = engineID
        if let first = labEngines.first(where: { $0.id == engineID })?.operations.first {
            selectedLabOperation = first.name
        }
        labInputJSON = labTemplate(engineID: selectedLabEngineID, operation: selectedLabOperation)
        labReceipt = nil
    }

    func selectLabOperation(_ operation: String) {
        selectedLabOperation = operation
        labInputJSON = labTemplate(engineID: selectedLabEngineID, operation: operation)
        labReceipt = nil
    }

    func runSelectedLabAdvisory() {
        guard runtimeCapabilities?.supportsCommand("run_lab_engine_advisory") == true,
              let missionID = activeMissionID,
              let taskID = activeLabTaskID,
              let engine = selectedLabEngine, engine.available,
              engine.operations.contains(where: { $0.name == selectedLabOperation }),
              !isBusy else { return }
        isBusy = true
        lastError = nil
        labControlMessage = "Running governed Lab advisory…"
        let engineID = selectedLabEngineID
        let operation = selectedLabOperation
        let input = labInputJSON
        Task {
            do {
                labReceipt = try await runtime.runLabAdvisory(
                    engineID: engineID, operation: operation, inputJSON: input,
                    missionID: missionID, taskID: taskID
                )
                labControlMessage = "Advisory recorded as proposed evidence; independent verification not performed."
                refreshHistory()
            } catch {
                handle(error)
                labControlMessage = "Lab advisory rejected or failed."
            }
            isBusy = false
        }
    }

    private func normalizeLabSelection() {
        guard !labEngines.isEmpty else { return }
        if !labEngines.contains(where: { $0.id == selectedLabEngineID }) {
            selectedLabEngineID = labEngines.first?.id ?? ""
        }
        guard let engine = selectedLabEngine else { return }
        if !engine.operations.contains(where: { $0.name == selectedLabOperation }) {
            selectedLabOperation = engine.operations.first?.name ?? ""
        }
        labInputJSON = labTemplate(engineID: selectedLabEngineID, operation: selectedLabOperation)
    }

    private func labTemplate(engineID: String, operation: String) -> String {
        switch (engineID, operation) {
        case ("lab.math", "cyclotomic_summary"):
            return "{\n  \"conductor\": 5\n}"
        case ("lab.math", "mcmillan_tc"):
            return "{\n  \"lambda\": 1.0,\n  \"omegaLog\": 300.0,\n  \"muStar\": 0.1\n}"
        case ("lab.analogy", "structural_map"):
            return "{\n  \"source\": {\"name\": \"fire\", \"roles\": {\"CAUSE\": \"fire\", \"EFFECT\": \"smoke\"}},\n  \"target\": {\"name\": \"bug\", \"roles\": {\"CAUSE\": \"bug\", \"EFFECT\": \"crash\"}}\n}"
        case ("lab.analogy", "schema_abstract"):
            return "{\n  \"structures\": [\n    {\"name\": \"one\", \"roles\": {\"CAUSE\": \"a\", \"EFFECT\": \"b\"}},\n    {\"name\": \"two\", \"roles\": {\"CAUSE\": \"c\", \"EFFECT\": \"d\"}}\n  ]\n}"
        case ("lab.consensus", "aggregate_beliefs"):
            return "{\n  \"beliefs\": [0.2, 0.8, 0.7]\n}"
        case ("lab.forge", "repository_archaeology"):
            return forgeRootTemplate(["root": targetRoot])
        case ("lab.forge", "gap_analysis"):
            return forgeRootTemplate(["root": targetRoot, "expectations": ["document current architecture", "preserve tests"]])
        case ("lab.forge", "sigma_brief"):
            return forgeRootTemplate(["root": targetRoot, "objective": "Strengthen the current implementation", "expectations": ["preserve tests", "preserve authority boundaries"]])
        case ("lab.forge", "forgeproof_score"):
            return "{\n  \"scores\": {\"Precision\": 4, \"Reusability\": 4, \"Safety\": 4, \"Auditability\": 4, \"Effectiveness\": 4},\n  \"notes\": {\"Assumptions\": \"bounded internal use\", \"Known limits\": \"not externally benchmarked\", \"Experimental elements\": \"none\", \"Confidence tag\": \"medium\"}\n}"
        default:
            return "{}"
        }
    }

    private func forgeRootTemplate(_ object: [String: Any]) -> String {
        guard JSONSerialization.isValidJSONObject(object),
              let data = try? JSONSerialization.data(withJSONObject: object, options: [.prettyPrinted, .sortedKeys]),
              let text = String(data: data, encoding: .utf8) else { return "{}" }
        return text
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
        refreshLabs()
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
