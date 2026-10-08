import Foundation
import Combine
import CAPTCoreDesktop
import Security

@MainActor
final class CAPTOperatorStore: ObservableObject {
    private static let appBundleVersion = Bundle.main.object(
        forInfoDictionaryKey: "CFBundleShortVersionString"
    ) as? String ?? "unknown"
    private static let startupMessage = CAPTChatMessage(
        role: .system,
        text: "CAPT native surface ready. Connect to RuntimeService to begin."
    )
    private static let defaultNewChatTargetRoot = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("CAPT_core", isDirectory: true).path

    @Published var connectionState: CAPTRuntimeConnectionState = .disconnected
    @Published var provider = "ollama"
    @Published var model = "qwen3.5-defiant-fable:latest"
    @Published var targetRoot = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("CAPT_core", isDirectory: true).path
    @Published var promptIntelligence = "AUTO"
    @Published var reasoningEffort = ""
    @Published var cohortEnabled = false
    @Published var vesselsPerCohort = 6
    @Published var councilBusy = false
    @Published var councilError: String?
    @Published var runtimeQueryOutput = ""
    @Published var runtimeQueryError: String?
    @Published var runtimeQueryBusy = false
    @Published var inspectedTaskID: String?
    @Published var inspectedTaskJSON = ""
    @Published var inspectingTask = false
    @Published var runtimeIdentity = "Not connected"
    @Published var taskState = "—"
    @Published var isBusy = false
    @Published var lastError: String?
    @Published var piRecoveryMessage: String?
    @Published var piRecoveryBusy = false
    @Published var missions: [CAPTMissionSummary] = []
    @Published var evidenceItems: [CAPTEvidenceSummary] = []
    @Published var approvals: [CAPTApprovalSummary] = []
    @Published var driverRuns: [CAPTDriverRunSummary] = []
    @Published var recentEvents: [CAPTEventSummary] = []
    @Published var bots: [CAPTBotSummary] = []
    @Published var botCreationBusy = false
    @Published var botCreationMessage = ""
    @Published var kanbanMessage = ""
    @Published var kanbanBusy = false
    @Published var providers: [CAPTProviderSnapshot] = []
    @Published var modelSnapshot: CAPTModelSelectionSnapshot?
    @Published var operatorStateError: String?
    @Published var verbosity = "normal"
    @Published var memorySnapshot: CAPTMemoryRuntimeSnapshot?
    @Published var checkpointSnapshot: CAPTCheckpointSnapshot?
    @Published var runtimeControlMessage = ""
    @Published var runtimeCapabilities: CAPTRuntimeCapabilitiesSnapshot?
    @Published var claimReview: CAPTClaimReviewSnapshot?
    @Published var reviewedClaimID: String?
    @Published var providerCredentialStatus: [String: String] = [:]
    @Published var providerWarmState = "not_required"
    @Published var providerWarmLatencyMs: Int?
    @Published var managedSkills: CAPTManagedSkillSnapshot?
    @Published var skillSelectionMode = "auto"
    @Published var selectedSkillNames: Set<String> = []
    @Published var skillManagementBusy = false
    @Published var skillManagementMessage = ""
    @Published var composerSeed: String?
    @Published var authoritySettings = CAPTExecutionAuthoritySettings.default
    @Published private var chatWorkspace = CAPTNativeChatWorkspace()
    var activePIRequestID: String? { chatWorkspace.activeSession?.piRequestID }

    private let runtime: CAPTBackgroundRuntime
    private let runtimeProfile: CAPTRuntimeProfile
    private let historyRuntime: CAPTBackgroundRuntime
    private let councilRuntime: CAPTBackgroundRuntime
    private let queryRuntime: CAPTBackgroundRuntime
    private let botRuntime: CAPTBackgroundRuntime
    private var historyRefreshPending = false
    private var compilingTasks: [UUID: Task<Void, Never>] = [:]
    private var compilationVersions: [UUID: UUID] = [:]
    private let sessionStore: CAPTEncryptedSessionStore
    let runtimeStateDirectory: String
    private var providerWarmIdentity: String?
    private var cachedOperatorProvider = "ollama"
    private var cachedOperatorModel = "qwen3.5-defiant-fable:latest"

    init(
        profile: CAPTRuntimeProfile = CAPTRuntimeProfile.current(),
        runtime: CAPTBackgroundRuntime? = nil,
        sessionStore: CAPTEncryptedSessionStore? = nil
    ) {
        self.runtime = runtime ?? CAPTBackgroundRuntime(profile: profile)
        self.runtimeProfile = profile
        self.historyRuntime = CAPTBackgroundRuntime(profile: profile)
        self.councilRuntime = CAPTBackgroundRuntime(profile: profile)
        self.queryRuntime = CAPTBackgroundRuntime(profile: profile)
        self.botRuntime = CAPTBackgroundRuntime(profile: profile)
        self.sessionStore = sessionStore ?? CAPTEncryptedSessionStore(
            fileURL: CAPTEncryptedSessionStore.defaultFileURL(profile: profile)
        )
        self.runtimeStateDirectory = profile.stateDirectory
        let defaults = UserDefaults.standard
        let storedMode = defaults.string(forKey: "capt.skillSelectionMode") ?? "auto"
        self.skillSelectionMode = ["auto", "manual", "off"].contains(storedMode) ? storedMode : "auto"
        self.selectedSkillNames = Set(defaults.stringArray(forKey: "capt.selectedSkillNames") ?? [])
        let storedReasoning = defaults.string(forKey: "capt.reasoningEffort") ?? ""
        let allowedReasoning = Set(["", "none", "minimal", "low", "medium", "high", "xhigh"])
        self.reasoningEffort = allowedReasoning.contains(storedReasoning) ? storedReasoning : ""
        if let data = defaults.data(forKey: "capt.executionAuthoritySettings"),
           let decoded = try? JSONDecoder().decode(CAPTExecutionAuthoritySettings.self, from: data) {
            self.authoritySettings = decoded
        }
        restoreSessionsAsync()
        refreshOperatorState()
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

    var promptProposal: CAPTPromptProposal? {
        chatWorkspace.activePromptProposal
    }

    var verificationDriverRunID: String? {
        chatWorkspace.activeSession?.verificationDriverRunID
    }

    var activeChatFlow: CAPTChatFlow {
        chatWorkspace.activeFlow
    }

    var isActiveChatBusy: Bool {
        activeChatFlow.isBusy
    }

    var canComposeInActiveChat: Bool {
        connectionState == .connected &&
            providerWarmState != "warming" &&
            pendingApproval == nil &&
            promptProposal == nil &&
            activeChatFlow.canCompose
    }

    func setExecutionProvider(_ value: String) {
        persistConfiguration(
            for: activeSessionID, provider: value, model: model, targetRoot: targetRoot
        )
    }

    func setExecutionModel(_ value: String) {
        persistConfiguration(
            for: activeSessionID, provider: provider, model: value, targetRoot: targetRoot
        )
    }

    func setExecutionTargetRoot(_ value: String) {
        persistConfiguration(
            for: activeSessionID, provider: provider, model: model, targetRoot: value
        )
    }

    func setCohortEnabled(_ enabled: Bool) {
        let count = enabled ? vesselsPerCohort : nil
        if activeSessionID == nil {
            cohortEnabled = enabled
            return
        }
        guard mutateWorkspace({ $0.setActiveCohortVessels(count) }) else { return }
        cohortEnabled = enabled
        saveSessions()
    }

    func setVesselsPerCohort(_ count: Int) {
        guard (1...1000).contains(count) else { return }
        if activeSessionID != nil, cohortEnabled {
            guard mutateWorkspace({ $0.setActiveCohortVessels(count) }) else { return }
            saveSessions()
        }
        vesselsPerCohort = count
    }

    func setReasoningEffort(_ value: String) {
        let allowed = Set(["", "none", "minimal", "low", "medium", "high", "xhigh"])
        guard allowed.contains(value) else { return }
        reasoningEffort = value
        UserDefaults.standard.set(value, forKey: "capt.reasoningEffort")
    }

    func reconcileActiveApprovalValidity(now: Date = Date()) {
        let previousRequestID = pendingApproval?.requestID
        mutateWorkspace { $0.reconcileActiveApprovalValidity(now: now) }
        guard previousRequestID != pendingApproval?.requestID else { return }
        updateTaskStateFromActiveFlow()
        lastError = chatWorkspace.activeSession?.messages.last?.text
        saveSessions()
        refreshHistory()
    }

    var providerWarmLabel: String {
        switch providerWarmState {
        case "warming": return "WARMING"
        case "warm":
            if let ms = providerWarmLatencyMs { return "WARM · \(ms) ms" }
            return "WARM"
        case "failed": return "WARMUP FAILED"
        default: return ""
        }
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
                // Only inspect the original durable attempt after restoring.
                // No automatic model dispatch or retry on launch.
                recoverPIRequest()
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
            defer { isBusy = false }
            do {
                let identity = try await runtime.connect()
                runtimeIdentity = "CAPT app \(Self.appBundleVersion) · checkpoint contract \(identity.runtimeVersion) · integrity \(identity.integrity)"
                connectionState = .connected
                let operatorSnapshot = try await runtime.operatorSnapshot()
                applyOperatorSnapshot(operatorSnapshot)
                await prewarmSelectedProviderIfNeeded()
                refreshIdentity()
                refreshHistory()
                refreshMemory()
                refreshCapabilities()
                refreshBots()
                refreshSkills()
                recoverPIRequest()
            } catch {
                let message = error.localizedDescription
                lastError = message
                connectionState = .failed(message)
                refreshOperatorState()
            }
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
            let defaults = newChatDefaults
            _ = mutateWorkspace {
                $0.newChat(
                    provider: defaults.providerID,
                    model: defaults.modelID,
                    targetRoot: defaults.targetRoot
                )
            }
            syncSelectionFromActiveSession()
        }

        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        // Persist before touching RuntimeService, including the exact attempt
        // identity used for both durable admission and read-only reattachment.
        let piRequestID = "pp-native-" + UUID().uuidString.lowercased()
        guard let sessionID = mutateWorkspace({
            $0.beginPrompt(trimmed, provider: provider, model: model,
                           targetRoot: targetRoot, piRequestID: piRequestID)
        }) else { return }

        saveSessions()
        lastError = nil
        piRecoveryMessage = nil
        if activeSessionID == sessionID { taskState = "proposal_compiling" }

        let selectedProvider = provider
        let selectedModel = model
        let root = targetRoot
        let intelligence = promptIntelligence
        let selectedReasoningEffort = reasoningEffort
        let remoteCompilationAuthorized = authoritySettings.remotePromptCompilationAllowed &&
            authoritySettings.providerNetwork == .remoteAllowed

        // Each submitted PI request has its own authenticated actor and socket.
        // Abandoning one wait must not queue every future chat behind it.
        let proposalRuntime = CAPTBackgroundRuntime(profile: runtimeProfile)
        let compilationVersion = UUID()
        compilationVersions[sessionID] = compilationVersion
        compilingTasks[sessionID] = Task {
            defer {
                if compilationVersions[sessionID] == compilationVersion {
                    compilationVersions.removeValue(forKey: sessionID)
                    compilingTasks.removeValue(forKey: sessionID)
                }
            }
            do {
                // PI uses an isolated actor/socket; never serialize the whole
                // operator control plane behind a remote compiler request.
                _ = try await proposalRuntime.connect()
                let proposal = try await proposalRuntime.compileProposal(
                    original: trimmed, targetRoot: root, provider: selectedProvider,
                    model: selectedModel, promptIntelligence: intelligence,
                    reasoningEffort: selectedReasoningEffort,
                    remoteCompilationAuthorized: remoteCompilationAuthorized,
                    piRequestID: piRequestID
                )
                guard !Task.isCancelled,
                      compilationVersions[sessionID] == compilationVersion else { return }
                mutateWorkspace { $0.receiveProposal(proposal, for: sessionID) }
                if activeSessionID == sessionID {
                    updateTaskStateFromActiveFlow()
                    if proposal.status != "ready_for_approval" {
                        lastError = proposal.unresolvedQuestions.first
                    }
                }
                saveSessions()
                refreshHistory()
            } catch {
                guard !Task.isCancelled,
                      compilationVersions[sessionID] == compilationVersion else { return }
                let message = error.localizedDescription
                mutateWorkspace { $0.failProposalRequest(message: message, for: sessionID) }
                if activeSessionID == sessionID {
                    taskState = "proposal_error"
                    lastError = message
                }
                saveSessions()
                recoverPIRequest(for: sessionID)
            }
        }
    }

    func abandonCompilingProposal() {
        guard let sessionID = activeSessionID,
              activeChatFlow.phase == .compilingProposal else { return }
        compilationVersions.removeValue(forKey: sessionID)
        compilingTasks.removeValue(forKey: sessionID)?.cancel()
        let message = "Stopped waiting for Prompt Intelligence locally. The request identity was preserved for read-only recovery. A remote request may still finish or incur usage; do not automatically resubmit."
        mutateWorkspace { $0.failProposalRequest(message: message, for: sessionID) }
        taskState = "proposal_abandoned"
        lastError = nil
        saveSessions()
    }

    func selectPromptProposal(
        _ selection: CAPTPromptSelection,
        editedPrompt: String = ""
    ) {
        guard let sessionID = activeSessionID, promptProposal != nil else { return }
        guard let proposal = mutateWorkspace({
            $0.beginProposalApproval(for: sessionID)
        }) else { return }
        taskState = "approval_preparing"
        lastError = nil
        let missionID = chatWorkspace.session(sessionID)?.missionID
        let skillSelection = executionSkillSelection()
        let cohortSpec: [String: Any]?
        if let vessels = chatWorkspace.session(sessionID)?.cohortVessels {
            cohortSpec = [
                "cohortId": "native-" + proposal.proposalID,
                "configurationId": "native-chat-v2",
                "vesselsPerCohort": vessels,
                "vesselCharterPolicy": ["schemaVersion": "2.0.0"]
            ]
        } else {
            cohortSpec = nil
        }

        Task {
            do {
                let pending = try await runtime.requestApproval(
                    proposal: proposal, selection: selection, editedPrompt: editedPrompt,
                    missionID: missionID, managedSkillNames: skillSelection.names,
                    autoSelectSkills: skillSelection.autoSelect,
                    cohortSpec: cohortSpec,
                    authoritySettings: authoritySettings
                )
                mutateWorkspace { $0.receiveApproval(pending, for: sessionID) }
                if activeSessionID == sessionID { updateTaskStateFromActiveFlow() }
                saveSessions()
                refreshHistory()
            } catch {
                let message = error.localizedDescription
                mutateWorkspace { $0.failApprovalRequest(message: message, for: sessionID) }
                if activeSessionID == sessionID {
                    updateTaskStateFromActiveFlow()
                    lastError = message
                }
                saveSessions()
            }
        }
    }

    func cancelPromptProposal() {
        guard let sessionID = activeSessionID, let proposal = promptProposal else { return }
        lastError = nil
        Task {
            do {
                try await runtime.cancelProposal(proposal)
                mutateWorkspace { $0.completeProposalCancellation(for: sessionID) }
                if activeSessionID == sessionID { updateTaskStateFromActiveFlow() }
                saveSessions()
                refreshHistory()
            } catch {
                if activeSessionID == sessionID { lastError = error.localizedDescription }
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
                        driverRunID: result.driverRunID,
                        executionDetailsJSON: result.executionDetailsJSON,
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

    func reviewProviderResult(disposition: String, note: String) {
        guard let sessionID = activeSessionID,
              let driverRunID = verificationDriverRunID,
              ["accept", "reject"].contains(disposition) else { return }
        isBusy = true
        lastError = nil
        Task {
            defer { isBusy = false }
            do {
                let result = try await runtime.reviewProviderResult(
                    driverRunID: driverRunID, disposition: disposition, note: note
                )
                let accepted = disposition == "accept"
                mutateWorkspace { $0.completeVerification(accepted: accepted, for: sessionID) }
                if activeSessionID == sessionID {
                    taskState = (result["taskState"] as? String) ?? (accepted ? "succeeded" : "failed")
                }
                saveSessions()
                refreshHistory()
            } catch {
                if activeSessionID == sessionID { lastError = error.localizedDescription }
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
                let identity = try await runtime.identity()
                runtimeIdentity = "CAPT app \(Self.appBundleVersion) · checkpoint contract \(identity.runtimeVersion) · integrity \(identity.integrity)"
            } catch {
                handleGlobal(error)
            }
        }
    }

    func refreshHistory() {
        guard connectionState == .connected, !historyRefreshPending else { return }
        historyRefreshPending = true
        Task {
            defer { historyRefreshPending = false }
            do {
                // Expensive forensic projection uses its own authenticated socket;
                // thousands of aggregate reads cannot block chat/control actions.
                _ = try await historyRuntime.connect()
                let snapshot = try await historyRuntime.historySnapshot()
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

    private func applyOperatorSnapshot(_ snapshot: CAPTOperatorStateSnapshot) {
        providers = snapshot.providers
        modelSnapshot = snapshot.models
        verbosity = snapshot.verbosity
        operatorStateError = nil
        let selection = CAPTOperatorPreferenceResolver.resolve(
            providers: snapshot.providers,
            models: snapshot.models,
            fallbackProvider: cachedOperatorProvider,
            fallbackModel: cachedOperatorModel
        )
        cachedOperatorProvider = selection.providerID
        cachedOperatorModel = selection.modelID
        if activeSessionID == nil {
            provider = selection.providerID
            model = selection.modelID
        }
    }

    private func warmupTarget() -> CAPTProviderSnapshot? {
        let selected = providers.first(where: { $0.id == provider }) ??
            providers.first(where: { $0.selected })
        guard let selected, CAPTOperatorCLI.requiresPrewarm(selected, modelID: model) else {
            return nil
        }
        return selected
    }

    private func prewarmSelectedProviderIfNeeded() async {
        guard let selected = warmupTarget() else {
            providerWarmState = "not_required"
            providerWarmLatencyMs = nil
            providerWarmIdentity = nil
            return
        }
        let identity = selected.id + "/" + model
        if providerWarmState == "warm", providerWarmIdentity == identity { return }
        providerWarmState = "warming"
        providerWarmLatencyMs = nil
        do {
            let result = try await runtime.prewarmProvider(providerID: selected.id, modelID: model)
            providerWarmState = result.status
            providerWarmLatencyMs = result.latencyMs
            providerWarmIdentity = identity
            runtimeControlMessage = "Provider warm: \(identity)"
        } catch {
            providerWarmState = "failed"
            providerWarmLatencyMs = nil
            providerWarmIdentity = nil
            runtimeControlMessage = "Provider warmup failed: " + error.localizedDescription
        }
    }

    private func scheduleSelectedProviderPrewarmIfNeeded() {
        guard let selected = warmupTarget() else {
            providerWarmState = "not_required"
            providerWarmLatencyMs = nil
            providerWarmIdentity = nil
            return
        }
        let identity = selected.id + "/" + model
        if providerWarmState == "warm", providerWarmIdentity == identity { return }
        providerWarmState = "warming"
        providerWarmLatencyMs = nil
        Task { await prewarmSelectedProviderIfNeeded() }
    }

    func refreshOperatorState() {
        Task {
            do { applyOperatorSnapshot(try await runtime.operatorSnapshot()) }
            catch { operatorStateError = error.localizedDescription }
        }
    }

    var operatorPreferenceSelection: CAPTOperatorPreferenceSelection {
        guard let modelSnapshot else {
            return CAPTOperatorPreferenceSelection(
                providerID: cachedOperatorProvider,
                modelID: cachedOperatorModel
            )
        }
        return CAPTOperatorPreferenceResolver.resolve(
            providers: providers,
            models: modelSnapshot,
            fallbackProvider: cachedOperatorProvider,
            fallbackModel: cachedOperatorModel
        )
    }

    private var newChatDefaults: CAPTNewChatDefaults {
        let operatorSelection = operatorPreferenceSelection
        return CAPTNewChatDefaultsResolver.resolve(
            operatorProvider: operatorSelection.providerID,
            operatorModel: operatorSelection.modelID,
            defaultTargetRoot: Self.defaultNewChatTargetRoot,
            activeSessionProvider: chatWorkspace.activeSession?.provider,
            activeSessionModel: chatWorkspace.activeSession?.model,
            activeSessionTargetRoot: chatWorkspace.activeSession?.targetRoot
        )
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

    func refreshBots() {
        guard connectionState == .connected else { return }
        Task {
            do { bots = try await runtime.botsSnapshot().bots }
            catch { lastError = error.localizedDescription }
        }
    }

    func refreshSkills() {
        guard connectionState == .connected else { return }
        Task {
            do {
                applyManagedSkillSnapshot(try await runtime.managedSkillsSnapshot())
            } catch {
                lastError = error.localizedDescription
            }
        }
    }

    private func applyManagedSkillSnapshot(_ snapshot: CAPTManagedSkillSnapshot) {
        managedSkills = snapshot
        let installed = Set(snapshot.skills.map(\.name))
        let filtered = selectedSkillNames.intersection(installed)
        if filtered != selectedSkillNames {
            selectedSkillNames = filtered
            persistSkillPreferences()
        }
    }

    func installManagedSkill(from sourcePath: String) {
        guard connectionState == .connected, !skillManagementBusy else { return }
        skillManagementBusy = true
        skillManagementMessage = "Installing and verifying managed skill…"
        lastError = nil
        Task {
            defer { skillManagementBusy = false }
            do {
                let result = try await runtime.installManagedSkill(sourcePath: sourcePath)
                applyManagedSkillSnapshot(try await runtime.managedSkillsSnapshot())
                skillManagementMessage =
                    "Verified \(result.skillNames.count) managed skills · \(result.manifestDigest.prefix(20))…"
            } catch {
                skillManagementMessage = ""
                lastError = error.localizedDescription
            }
        }
    }

    func createManagedSkill(
        name: String, description: String, version: String, body: String
    ) {
        guard connectionState == .connected, !skillManagementBusy else { return }
        skillManagementBusy = true
        skillManagementMessage = "Creating and verifying managed skill…"
        lastError = nil
        Task {
            defer { skillManagementBusy = false }
            do {
                let result = try await runtime.createManagedSkill(
                    name: name, description: description, version: version, body: body
                )
                applyManagedSkillSnapshot(try await runtime.managedSkillsSnapshot())
                skillManagementMessage =
                    "Created \(name) · pack now contains \(result.skillNames.count) verified skills."
            } catch {
                skillManagementMessage = ""
                lastError = error.localizedDescription
            }
        }
    }

    func beginGuidedSkillCreation() {
        composerSeed = """
        Guide me interactively in designing a new CAPT managed Agent Skill. Start by helping me sharpen the skill's mission, triggers, scope boundaries, failure modes, and verification criteria. Do not fabricate requirements I have not chosen. When the design is settled, produce a complete production-ready SKILL.md with valid frontmatter fields `name`, `description`, and `version`, followed by precise operational instructions. The final skill must be suitable for installation through CAPT's Skills tab.
        """
        newChat()
    }

    func takeComposerSeed() -> String? {
        let seed = composerSeed
        composerSeed = nil
        return seed
    }

    func setSkillSelectionMode(_ mode: String) {
        guard ["auto", "manual", "off"].contains(mode) else { return }
        skillSelectionMode = mode
        persistSkillPreferences()
    }

    func toggleSkill(_ name: String) {
        guard managedSkills?.skills.contains(where: { $0.name == name }) == true else { return }
        if selectedSkillNames.contains(name) {
            selectedSkillNames.remove(name)
        } else {
            selectedSkillNames.insert(name)
        }
        if skillSelectionMode == "auto" { skillSelectionMode = "manual" }
        persistSkillPreferences()
    }

    private func executionSkillSelection() -> (names: [String]?, autoSelect: Bool) {
        switch skillSelectionMode {
        case "manual":
            let installed = Set(managedSkills?.skills.map(\.name) ?? [])
            let names = selectedSkillNames.intersection(installed).sorted()
            if names.isEmpty { return (nil, false) }
            return (names, false)
        case "off":
            return (nil, false)
        default:
            return (nil, true)
        }
    }

    private func persistSkillPreferences() {
        let defaults = UserDefaults.standard
        defaults.set(skillSelectionMode, forKey: "capt.skillSelectionMode")
        defaults.set(selectedSkillNames.sorted(), forKey: "capt.selectedSkillNames")
    }

    func setAuthoritySettings(_ settings: CAPTExecutionAuthoritySettings) {
        guard settings != authoritySettings else { return }
        authoritySettings = settings
        if let data = try? JSONEncoder().encode(settings) {
            UserDefaults.standard.set(data, forKey: "capt.executionAuthoritySettings")
        }
        mutateWorkspace {
            $0.invalidateActiveAuthority(reason: "Execution authority settings changed.")
        }
        updateTaskStateFromActiveFlow()
        saveSessions()
    }

    var effectiveAuthorityFilesystemRoot: String? {
        authoritySettings.effectiveFilesystemRoot(projectRoot: targetRoot)
    }

    var selectedProviderRequiresRemoteNetwork: Bool {
        guard let snapshot = providers.first(where: { $0.id == provider }) else { return false }
        return snapshot.kind.lowercased() != "local"
    }

    var selectedProviderBlockedByNetworkAuthority: Bool {
        authoritySettings.providerNetwork == .localOnly && selectedProviderRequiresRemoteNetwork
    }

    var runtimeCompatibilityIssue: String? {
        guard connectionState == .connected, let capabilities = runtimeCapabilities else { return nil }
        let requiredQueries = ["managed_skills", "bots"]
        let requiredCommands = [
            "compile_prompt_proposal",
            "request_prompt_proposal_approval",
            "run_approved_hermes_inspection",
            "install_managed_skill",
            "create_managed_skill",
        ]
        let missingQueries = requiredQueries.filter { !capabilities.supportsQuery($0) }
        let missingCommands = requiredCommands.filter { !capabilities.supportsCommand($0) }
        let missing = missingQueries + missingCommands
        guard !missing.isEmpty else { return nil }
        return "Runtime API is older than this GUI · missing " + missing.joined(separator: ", ")
    }

    func refreshAll() {
        refreshIdentity()
        refreshHistory()
        refreshOperatorState()
        refreshMemory()
        refreshCapabilities()
        refreshBots()
        refreshSkills()
    }

    var pendingApprovals: [CAPTApprovalSummary] {
        approvals.filter { $0.isActionable() }
    }

    func decideQueuedApproval(_ item: CAPTApprovalSummary, decision: String) {
        guard !isBusy, item.isActionable() else { return }
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
        isBusy = true
        Task {
            defer { isBusy = false }
            do {
                providers = try await runtime.activateProvider(providerID)
                applyOperatorSnapshot(try await runtime.operatorSnapshot())
            } catch {
                operatorStateError = error.localizedDescription
            }
        }
    }

    func testProvider(_ providerID: String) {
        guard !isBusy else { return }
        isBusy = true
        Task {
            defer { isBusy = false }
            do {
                providers = try await runtime.testProvider(providerID)
                if let tested = providers.first(where: { $0.id == providerID }),
                   tested.health == "green" {
                    let latency = tested.latencyMs.map { " · \($0) ms" } ?? ""
                    providerCredentialStatus[providerID] = "Authenticated ✓\(latency)"
                    if providerID == provider { await prewarmSelectedProviderIfNeeded() }
                }
            } catch { handleGlobal(error) }
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
            handleGlobal(error)
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
            handleGlobal(error)
            return false
        }
    }

    func setDefaultModel(providerID: String, modelID: String) {
        guard !isBusy else { return }
        isBusy = true
        Task {
            defer { isBusy = false }
            do {
                modelSnapshot = try await runtime.setDefaultModel(
                    providerID: providerID,
                    modelID: modelID
                )
                applyOperatorSnapshot(try await runtime.operatorSnapshot())
            } catch {
                operatorStateError = error.localizedDescription
            }
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
                    retrieval: retrieval,
                    compression: compression,
                    checkpoint: checkpoint,
                    consolidation: consolidation,
                    hardStop: hardStop,
                    modelSafe: modelSafe
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
                claimReview = try await runtime.claimReview(
                    claimID: item.id,
                    statement: item.statement
                )
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
        chatWorkspace.activeSession?.missionID
    }

    var activeSessionTitle: String {
        chatWorkspace.activeSession?.title ?? "CAPT Chat"
    }

    func newChat() {
        // Never await RuntimeService or provider inference before opening a local
        // session. A remote PI stage can occupy a runtime actor for minutes.
        // Cached operator preferences are already refreshed independently.
        let defaults = newChatDefaults
        _ = mutateWorkspace {
            $0.newChat(
                provider: defaults.providerID,
                model: defaults.modelID,
                targetRoot: defaults.targetRoot
            )
        }
        syncSelectionFromActiveSession()
        taskState = "—"
        lastError = nil
        runtimeControlMessage = ""
        saveSessions()
        scheduleSelectedProviderPrewarmIfNeeded()
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
        cohortEnabled = session.cohortVessels != nil
        vesselsPerCohort = session.cohortVessels ?? 6
    }

    private func persistConfiguration(
        for sessionID: UUID?,
        provider newProvider: String,
        model newModel: String,
        targetRoot newTargetRoot: String
    ) {
        if let sessionID {
            mutateWorkspace {
                $0.updateConfiguration(
                    for: sessionID,
                    provider: newProvider,
                    model: newModel,
                    targetRoot: newTargetRoot
                )
            }
            saveSessions()
            guard activeSessionID == sessionID else { return }
            updateTaskStateFromActiveFlow()
            lastError = activeChatFlow.phase == .recoverableFailure
                ? chatWorkspace.activeSession?.messages.last?.text
                : nil
        }
        provider = newProvider
        model = newModel
        targetRoot = newTargetRoot
    }

    private func updateTaskStateFromActiveFlow() {
        if pendingApproval != nil {
            taskState = "approval_required"
            return
        }
        switch activeChatFlow.phase {
        case .idle: taskState = "—"
        case .compilingProposal: taskState = "proposal_compiling"
        case .reviewingProposal: taskState = "proposal_review"
        case .requestingApproval: taskState = "approval_preparing"
        case .awaitingApproval: taskState = "approval_required"
        case .executing: taskState = "executing"
        case .awaitingVerification: taskState = "awaiting_verification"
        case .executionIndeterminate: taskState = "indeterminate"
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

    private func handleGlobal(_ error: Error) {
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


// MARK: - Native governed multi-cohort council
// Council state belongs to the originating encrypted chat session. Human
// decisions remain explicit; RuntimeService, not Swift, authorizes dispatch.
extension CAPTOperatorStore {
    var activeCouncil: CAPTCouncilReview? {
        chatWorkspace.activeSession?.councilReview
    }

    func prepareCouncil(
        objective: String, configurations: [(provider: String, model: String)],
        vessels: Int, concurrency: Int
    ) {
        guard connectionState == .connected, !councilBusy,
              canComposeInActiveChat else { return }
        if activeSessionID == nil { newChat() }
        guard let sessionID = activeSessionID,
              chatWorkspace.session(sessionID)?.councilReview == nil else { return }
        let cleaned = objective.trimmingCharacters(in: .whitespacesAndNewlines)
        let suffix = UUID().uuidString.lowercased()
        do {
            let cohorts = configurations.enumerated().map { index, selection in
                CAPTCouncilCohort(
                    id: "cohort-" + suffix + "-" + String(index + 1),
                    provider: selection.provider.trimmingCharacters(in: .whitespacesAndNewlines),
                    model: selection.model.trimmingCharacters(in: .whitespacesAndNewlines),
                    vessels: vessels
                )
            }
            let review = try CAPTCouncilReview(
                id: "council-native-" + suffix,
                missionID: "m-native-council-" + suffix,
                objective: cleaned, targetRoot: targetRoot,
                maxConcurrentCohorts: concurrency, cohorts: cohorts
            )
            mutateWorkspace { $0.updateCouncil(review, for: sessionID) }
            saveSessions()
            prepareRemainingCouncilCohorts(sessionID: sessionID)
        } catch {
            councilError = error.localizedDescription
        }
    }

    func prepareRemainingCouncilCohorts(sessionID: UUID? = nil) {
        guard !councilBusy,
              let id = sessionID ?? activeSessionID,
              let initial = chatWorkspace.session(id)?.councilReview else { return }
        councilBusy = true
        councilError = nil
        Task {
            defer { councilBusy = false }
            do {
                _ = try await councilRuntime.connect()
                for index in initial.cohorts.indices {
                    guard var latest = chatWorkspace.session(id)?.councilReview,
                          latest.id == initial.id else { return }
                    if latest.cohorts[index].requestID != nil { continue }
                    let prepared = try await councilRuntime.prepareCouncilCohort(latest, index: index)
                    latest.cohorts[index] = prepared
                    mutateWorkspace { $0.updateCouncil(latest, for: id) }
                    saveSessions() // durable partial requests; never duplicate on retry
                }
                refreshCouncil(sessionID: id)
            } catch {
                councilError = error.localizedDescription
            }
        }
    }

    func refreshCouncil(sessionID: UUID? = nil) {
        guard !councilBusy || sessionID != nil,
              let id = sessionID ?? activeSessionID,
              let initial = chatWorkspace.session(id)?.councilReview else { return }
        Task {
            do {
                _ = try await councilRuntime.connect()
                for index in initial.cohorts.indices {
                    guard var latest = chatWorkspace.session(id)?.councilReview,
                          latest.id == initial.id else { return }
                    let state = try await councilRuntime.councilCohortState(latest.cohorts[index])
                    latest.cohorts[index] = state
                    mutateWorkspace { $0.updateCouncil(latest, for: id) }
                    saveSessions()
                }
            } catch {
                councilError = error.localizedDescription
            }
        }
    }

    func decideCouncilCohort(at index: Int, approve: Bool) {
        guard !councilBusy,
              let id = activeSessionID,
              let review = chatWorkspace.session(id)?.councilReview,
              review.cohorts.indices.contains(index) else { return }
        councilBusy = true
        councilError = nil
        Task {
            defer { councilBusy = false }
            do {
                _ = try await councilRuntime.connect()
                let updated = try await councilRuntime.decideCouncilCohort(
                    review.cohorts[index], approve: approve
                )
                guard var latest = chatWorkspace.session(id)?.councilReview,
                      latest.id == review.id else { return }
                latest.cohorts[index] = updated
                mutateWorkspace { $0.updateCouncil(latest, for: id) }
                saveSessions()
                refreshHistory()
            } catch {
                councilError = error.localizedDescription
            }
        }
    }

    func runCouncil() {
        guard !councilBusy,
              let id = activeSessionID,
              let review = chatWorkspace.session(id)?.councilReview,
              review.canRunOrReattach else { return }
        councilBusy = true
        councilError = nil
        Task {
            defer { councilBusy = false }
            do {
                _ = try await councilRuntime.connect()
                let receipt = try await councilRuntime.runCouncil(review)
                guard var latest = chatWorkspace.session(id)?.councilReview,
                      latest.id == review.id else { return }
                // Complete evidence and receipts remain in RuntimeService.
                // Limit the native encrypted preview, not the authoritative record.
                latest.executionReceipt = String(receipt.prefix(32_000))
                latest.message = "Council dispatch receipt recorded. Inspect Missions and Evidence for independent verification."
                mutateWorkspace { $0.updateCouncil(latest, for: id) }
                saveSessions()
                refreshHistory()
            } catch {
                councilError = error.localizedDescription
                refreshCouncil(sessionID: id)
            }
        }
    }
}


extension CAPTOperatorStore {
    func performReadOnlyRuntimeQuery(_ operation: String, payloadJSON: String) {
        guard connectionState == .connected, !runtimeQueryBusy else { return }
        runtimeQueryBusy = true
        runtimeQueryError = nil
        runtimeQueryOutput = ""
        Task {
            defer { runtimeQueryBusy = false }
            do {
                _ = try await queryRuntime.connect()
                runtimeQueryOutput = try await queryRuntime.readRuntimeQuery(
                    operation: operation, payloadJSON: payloadJSON
                )
            } catch {
                runtimeQueryError = error.localizedDescription
            }
        }
    }
}


extension CAPTOperatorStore {
    /// Read a task and its run from RuntimeService, never local ledger SQL.
    func inspectMissionTask(_ taskID: String, runID: String?) {
        guard !inspectingTask, connectionState == .connected else { return }
        inspectingTask = true
        inspectedTaskID = taskID
        inspectedTaskJSON = "Reading authoritative task state…"
        Task {
            defer { inspectingTask = false }
            do {
                _ = try await queryRuntime.connect()
                let taskPayload = try JSONSerialization.data(
                    withJSONObject: ["streamId": "task-" + taskID]
                )
                var text = try await queryRuntime.readRuntimeQuery(
                    operation: "get_state",
                    payloadJSON: String(decoding: taskPayload, as: UTF8.self)
                )
                if let runID {
                    let runPayload = try JSONSerialization.data(
                        withJSONObject: ["streamId": "driverrun-" + runID]
                    )
                    let runText = try await queryRuntime.readRuntimeQuery(
                        operation: "get_state",
                        payloadJSON: String(decoding: runPayload, as: UTF8.self)
                    )
                    text += "\n\nDRIVER RUN STATE\n" + runText
                }
                inspectedTaskJSON = text
            } catch {
                inspectedTaskJSON = "Runtime read failed: " + error.localizedDescription
            }
        }
    }
}

extension CAPTOperatorStore {
    func createBot(_ draft: CAPTBotDraft) {
        guard connectionState == .connected,
              !botCreationBusy,
              runtimeCapabilities?.supportsCommand("register_bot") == true else {
            botCreationMessage = "RuntimeService Bot registration is unavailable. Reconnect to the updated governed runtime."
            return
        }
        botCreationBusy = true
        botCreationMessage = "Registering identity and policy…"
        Task {
            defer { botCreationBusy = false }
            do {
                _ = try await botRuntime.connect()
                let id = try await botRuntime.registerBot(draft)
                botCreationMessage = "Registered " + id +
                    ". No tools or autonomous execution are granted by registration."
                refreshBots()
            } catch {
                botCreationMessage = "Registration refused: " + error.localizedDescription
            }
        }
    }
}

extension CAPTOperatorStore {
    /// Prepare a governed successor request in Chat. Merely navigating here
    /// never changes task state or dispatches a model/tool.
    func prepareKanbanContinuation(_ card: CAPTKanbanCard) {
        composerSeed = """
        Continue the existing CAPT mission with authoritative provenance:
        Mission: \(card.task.missionID)
        Task: \(card.task.id)
        Stored task state: \(card.task.state)
        Stored mission state: \(card.missionState)
        Existing driver run: \(card.run?.id ?? "none")
        Dependencies: \(card.task.dependencies.joined(separator: ", "))
        Original objective: \(card.task.title)

        First inspect EventStore task/mission/DriverRun receipts, current GitHub
        issue status and any prior artifacts before proposing any new work.
        Distinguish previously completed work from unverified work. Provide
        a smallest-next-step plan, exact requirements, bounded authority, and
        human approval requests as needed. Never assume a suspended task is
        running or automatically retry an indeterminate external effect.
        Do not claim verified completion without independent evidence.
        """
        newChat()
    }

    /// Human-only verification pathway. Caller must inspect the receipt and
    /// explicitly enter an evidence-based note; this does not auto-approve.
    func reviewKanbanResult(_ card: CAPTKanbanCard, decision: String, note: String) {
        let trimmed = note.trimmingCharacters(in: .whitespacesAndNewlines)
        guard ["accept", "reject"].contains(decision),
              card.task.state == "awaiting_verification",
              let run = card.run, run.state == "completed",
              !trimmed.isEmpty,
              connectionState == .connected,
              !kanbanBusy else {
            kanbanMessage = "Review requires a completed DriverRun, an awaiting-verification task, and an explicit evidence note."
            return
        }
        kanbanBusy = true
        kanbanMessage = "Recording human verification for " + card.task.id + "…"
        Task {
            defer { kanbanBusy = false }
            do {
                let response = try await runtime.reviewProviderResult(
                    driverRunID: run.id, disposition: decision, note: trimmed
                )
                kanbanMessage = "RuntimeService response for " + card.task.id +
                    ": " + (response["taskState"] as? String ?? "unknown") +
                    ". Check Evidence before asserting mission completion."
                refreshHistory()
            } catch {
                kanbanMessage = "Human verification refused: " + error.localizedDescription
            }
        }
    }
}

extension CAPTOperatorStore {
    /// Read-only reconstruction from the original durable PI attempt.
    /// Reconnect MUST NOT call compile_prompt_proposal again.
    func recoverPIRequest(for specificSessionID: UUID? = nil) {
        guard !piRecoveryBusy,
              let session = specificSessionID.flatMap({ chatWorkspace.session($0) })
                  ?? chatWorkspace.activeSession,
              let requestID = session.piRequestID,
              session.promptProposal == nil else { return }
        let sessionID = session.id
        piRecoveryBusy = true
        if activeSessionID == sessionID {
            piRecoveryMessage = "Checking durable PI attempt " + requestID + "…"
        }
        let recoveryRuntime = CAPTBackgroundRuntime(profile: runtimeProfile)
        Task {
            defer { piRecoveryBusy = false }
            do {
                try await recoveryRuntime.connectReadOnly()
                let status = try await recoveryRuntime.piRequestStatus(requestID)
                guard chatWorkspace.session(sessionID)?.piRequestID == requestID else { return }
                let kind = status["status"] as? String ?? "unknown"
                switch kind {
                case "completed":
                    guard let data = status["proposal"] as? [String: Any] else {
                        throw CAPTRuntimeClientError.malformedResponse("PI proposal missing from completed receipt")
                    }
                    let proposal = try CAPTPromptProposal(dictionary: data)
                    mutateWorkspace { $0.receiveProposal(proposal, for: sessionID) }
                    if activeSessionID == sessionID {
                        updateTaskStateFromActiveFlow()
                        piRecoveryMessage = "Recovered PI proposal " + proposal.proposalID + " from EventStore. No second provider call."
                        lastError = nil
                    }
                    saveSessions()
                case "in_progress":
                    if activeSessionID == sessionID {
                        piRecoveryMessage = "Original PI request remains active. Check status again; no duplicate call was made."
                    }
                case "indeterminate", "failed", "not_found":
                    let detail = status["detail"] as? String ?? "Original PI attempt has no confirmed result."
                    let message = "PI " + kind + ": " + detail +
                        " Do not retry automatically; a prior attempt may have incurred usage."
                    mutateWorkspace { $0.failProposalRequest(message: message, for: sessionID) }
                    if activeSessionID == sessionID {
                        piRecoveryMessage = message
                        taskState = "proposal_reconciliation_required"
                    }
                    saveSessions()
                default:
                    piRecoveryMessage = "PI recovery returned an unrecognized state. Do not retry."
                }
            } catch {
                if activeSessionID == sessionID {
                    piRecoveryMessage = "PI status unavailable: " + error.localizedDescription +
                        ". No new model call was sent."
                }
            }
        }
    }
}
