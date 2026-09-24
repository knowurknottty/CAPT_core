import SwiftUI
import CAPTCoreDesktop

struct ChatView: View {
    @ObservedObject var store: CAPTOperatorStore
    @State private var draft = ""
    @State private var verificationNote = ""

    var body: some View {
        VStack(spacing: 0) {
            ChatContextRail(store: store)
            InversionDivider()

            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: 16) {
                        ForEach(store.messages) { message in
                            MessageRow(message: message)
                                .id(message.id)
                        }

                        if store.activeChatFlow.phase == .compilingProposal {
                            ChatProgressCard(
                                title: "Compiling Prompt Intelligence",
                                detail: "CAPT is running the governed prompt stage chain before any HumanApproval exists.",
                                tone: .violet
                            )
                            .id("chat-compiling-proposal")
                        }

                        if let proposal = store.promptProposal,
                           store.activeChatFlow.showsProposalControls {
                            PromptProposalCard(
                                proposal: proposal,
                                isBusy: store.isActiveChatBusy,
                                select: { selection, edited in
                                    store.selectPromptProposal(selection, editedPrompt: edited)
                                },
                                cancel: store.cancelPromptProposal
                            )
                            .id("prompt-proposal-" + proposal.proposalID)
                        }

                        if store.activeChatFlow.phase == .requestingApproval {
                            ChatProgressCard(
                                title: "Binding HumanApproval",
                                detail: "Prompt, provider, model, target, skills, context, and execution authority are being frozen into one approval identity.",
                                tone: .amber
                            )
                            .id("chat-requesting-approval")
                        }

                        if let pending = store.pendingApproval {
                            ApprovalCard(
                                pending: pending,
                                isBusy: store.isActiveChatBusy,
                                approve: store.approvePending,
                                deny: store.denyPending
                            )
                            .id("pending-approval")
                        }

                        if store.activeChatFlow.phase == .executing {
                            ChatProgressCard(
                                title: "Executing approved task",
                                detail: "The exact bound execution is running through CAPT RuntimeService. Model output remains evidence until independently verified.",
                                tone: .cyan
                            )
                            .id("chat-executing")
                        }

                        if store.activeChatFlow.phase == .awaitingVerification,
                           let driverRunID = store.verificationDriverRunID {
                            HumanVerificationCard(
                                driverRunID: driverRunID,
                                note: $verificationNote,
                                isBusy: store.isBusy,
                                accept: {
                                    store.reviewProviderResult(
                                        disposition: "accept", note: verificationNote
                                    )
                                },
                                reject: {
                                    store.reviewProviderResult(
                                        disposition: "reject", note: verificationNote
                                    )
                                }
                            )
                            .id("human-verification-" + driverRunID)
                        }
                    }
                    .padding(.horizontal, 28)
                    .padding(.vertical, 24)
                    .frame(maxWidth: 1040)
                    .frame(maxWidth: .infinity)
                }
                .onChange(of: store.messages.count) { _ in
                    if let id = store.messages.last?.id {
                        withAnimation(.easeInOut(duration: 0.18)) {
                            proxy.scrollTo(id, anchor: .bottom)
                        }
                    }
                }
                .onChange(of: store.pendingApproval?.requestID) { requestID in
                    guard requestID != nil else { return }
                    DispatchQueue.main.async {
                        withAnimation(.easeInOut(duration: 0.18)) {
                            proxy.scrollTo("pending-approval", anchor: .center)
                        }
                    }
                }
            }

            InversionDivider()
            ComposerView(
                draft: $draft,
                promptIntelligence: $store.promptIntelligence,
                reasoningEffort: Binding(
                    get: { store.reasoningEffort },
                    set: { store.setReasoningEffort($0) }
                ),
                remotePromptCompilationAllowed: Binding(
                    get: { store.authoritySettings.remotePromptCompilationAllowed },
                    set: { value in
                        var settings = store.authoritySettings
                        settings.remotePromptCompilationAllowed = value
                        store.setAuthoritySettings(settings)
                    }
                ),
                remotePromptCompilationAvailable:
                    store.authoritySettings.providerNetwork == .remoteAllowed,
                showRemotePromptCompilationControl: store.selectedProviderRequiresRemoteNetwork,
                enabled: store.canComposeInActiveChat,
                skillMode: store.skillSelectionMode,
                highRiskAuthority: store.authoritySettings.isHighRisk
            ) {
                guard store.canComposeInActiveChat else { return }
                let text = draft
                store.submitPrompt(text)
                draft = ""
            }
        }
        .navigationTitle(store.activeSessionTitle)
        .animation(.easeInOut(duration: 0.16), value: store.activeChatFlow.phase)
        .onAppear { seedComposerIfNeeded() }
        .onChange(of: store.composerSeed) { _ in seedComposerIfNeeded() }
        .task(id: store.pendingApproval?.requestID) {
            guard let expiresAt = store.pendingApproval?.expiresAt else { return }
            let delay = expiresAt.timeIntervalSinceNow
            if delay > 0 {
                try? await Task.sleep(for: .seconds(delay))
            }
            guard !Task.isCancelled else { return }
            store.reconcileActiveApprovalValidity()
        }
    }

    private func seedComposerIfNeeded() {
        guard draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              let seed = store.takeComposerSeed() else { return }
        draft = seed
    }
}

private struct ChatContextRail: View {
    @ObservedObject var store: CAPTOperatorStore

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 10) {
                HStack(spacing: 8) {
                    InversionBrandMark(compact: true)
                    Text(store.provider)
                        .font(.callout.weight(.semibold))
                    Text("/")
                        .foregroundStyle(.tertiary)
                    Text(store.model)
                        .font(.callout)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                }

                Spacer(minLength: 12)

                contextChip(
                    "PI", value: store.promptIntelligence,
                    symbol: "brain.head.profile", tone: .violet
                )
                contextChip(
                    "REASON", value: reasoningLabel,
                    symbol: "dial.high", tone: .cyan
                )
                contextChip(
                    "SKILLS", value: store.skillSelectionMode.uppercased(),
                    symbol: "puzzlepiece.extension", tone: .cyan
                )
                contextChip(
                    "AUTH", value: authorityLabel,
                    symbol: "lock.shield", tone: authorityTone
                )
                contextChip(
                    "ROOT", value: rootLabel,
                    symbol: "folder", tone: .neutral
                )
            }
            .padding(.horizontal, 18)
            .padding(.vertical, 9)

            if store.selectedProviderBlockedByNetworkAuthority {
                HStack(spacing: 8) {
                    Image(systemName: "network.slash")
                        .foregroundStyle(InversionTone.danger.color)
                    Text("Selected provider is remote, but Provider Network is Local only. Execution will fail closed until you choose a local provider or allow remote/cloud providers in Settings.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Spacer(minLength: 0)
                }
                .padding(.horizontal, 18)
                .padding(.vertical, 7)
                .background(InversionTone.danger.color.opacity(0.07))
                .overlay(alignment: .top) { InversionDivider() }
            }
        }
        .background(.ultraThinMaterial)
    }

    private var reasoningLabel: String {
        let frozen = store.pendingApproval?.reasoningEffort
            ?? store.promptProposal?.reasoningEffort
            ?? store.reasoningEffort
        return (frozen.isEmpty ? "DEFAULT" : frozen).uppercased()
    }

    private var authorityLabel: String {
        if store.selectedProviderBlockedByNetworkAuthority { return "BLOCKED" }
        return store.authoritySettings.isHighRisk ? "ELEVATED" : "BOUNDED"
    }

    private var authorityTone: InversionTone {
        if store.selectedProviderBlockedByNetworkAuthority { return .danger }
        return store.authoritySettings.isHighRisk ? .amber : .success
    }

    private var rootLabel: String {
        let url = URL(fileURLWithPath: store.targetRoot)
        let last = url.lastPathComponent
        return last.isEmpty ? store.targetRoot : last
    }

    private func contextChip(
        _ label: String,
        value: String,
        symbol: String,
        tone: InversionTone
    ) -> some View {
        HStack(spacing: 5) {
            Image(systemName: symbol)
                .font(.caption2)
                .foregroundStyle(tone.color)
            Text(label)
                .font(.system(size: 9, weight: .semibold))
                .tracking(0.65)
                .foregroundStyle(.tertiary)
            Text(value)
                .font(.caption2.monospaced().weight(.medium))
                .lineLimit(1)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 5)
        .background(Color.primary.opacity(0.04), in: Capsule())
    }
}

private struct MessageRow: View {
    let message: CAPTChatMessage
    @State private var showsExecutionDetails = false

    var body: some View {
        if message.role == .system {
            systemMessage
        } else {
            HStack(alignment: .top) {
                if message.role == .user { Spacer(minLength: 110) }
                messageSurface
                    .frame(maxWidth: 760, alignment: message.role == .user ? .trailing : .leading)
                if message.role != .user { Spacer(minLength: 110) }
            }
        }
    }

    private var messageSurface: some View {
        HStack(alignment: .top, spacing: 0) {
            if message.role != .user {
                Rectangle()
                    .fill(roleTone.color.opacity(0.8))
                    .frame(width: 2)
            }
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 8) {
                    Text(roleLabel)
                        .font(.caption2.weight(.semibold))
                        .tracking(0.85)
                        .foregroundStyle(roleTone.color)
                    if let state = message.authorityState {
                        InversionStatusBadge(state, monospaced: true)
                    }
                    Spacer(minLength: 0)
                    Text(message.timestamp.formatted(date: .omitted, time: .shortened))
                        .font(.caption2.monospacedDigit())
                        .foregroundStyle(.tertiary)
                }
                Text(message.text)
                    .textSelection(.enabled)
                    .font(.body)
                    .lineSpacing(2)
                if let details = message.executionDetailsJSON, !details.isEmpty {
                    DisclosureGroup("Execution details", isExpanded: $showsExecutionDetails) {
                        ScrollView([.vertical, .horizontal]) {
                            Text(details)
                                .font(.caption.monospaced())
                                .textSelection(.enabled)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(.top, 6)
                        }
                        .frame(maxHeight: 320)
                    }
                    .font(.caption)
                    .foregroundStyle(.secondary)
                }
            }
            .padding(14)
            if message.role == .user {
                Rectangle()
                    .fill(roleTone.color.opacity(0.8))
                    .frame(width: 2)
            }
        }
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 15, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 15, style: .continuous)
                .strokeBorder(roleTone.color.opacity(0.14), lineWidth: 1)
        }
    }

    private var systemMessage: some View {
        HStack(spacing: 8) {
            Image(systemName: "circle.hexagongrid")
                .foregroundStyle(InversionTone.cyan.color)
            Text(message.text)
                .font(.caption)
                .foregroundStyle(.secondary)
                .textSelection(.enabled)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 7)
        .background(Color.primary.opacity(0.035), in: Capsule())
        .frame(maxWidth: .infinity)
    }

    private var roleTone: InversionTone {
        message.role == .user ? .amber : .cyan
    }

    private var roleLabel: String {
        message.role == .user ? "OPERATOR" : "CAPT"
    }
}

private struct ChatProgressCard: View {
    let title: String
    let detail: String
    let tone: InversionTone

    var body: some View {
        InversionPanel(tone: tone) {
            HStack(alignment: .top, spacing: 12) {
                ProgressView()
                    .controlSize(.small)
                    .tint(tone.color)
                VStack(alignment: .leading, spacing: 4) {
                    Text(title).font(.headline)
                    Text(detail)
                        .font(.callout)
                        .foregroundStyle(.secondary)
                }
                Spacer()
            }
        }
        .frame(maxWidth: 760)
    }
}

private struct HumanVerificationCard: View {
    let driverRunID: String
    @Binding var note: String
    let isBusy: Bool
    let accept: () -> Void
    let reject: () -> Void

    var body: some View {
        InversionPanel(tone: .amber) {
            VStack(alignment: .leading, spacing: 14) {
                HStack(alignment: .top) {
                    InversionSectionHeader(
                        "Human verification required",
                        eyebrow: "HUMAN VERIFICATION BOUNDARY",
                        detail: "The provider run completed, but its completion claim is still proposed. Your disposition becomes HumanAttestation evidence; verification-plane classification and ClaimGuard promotion remain separate runtime authorities.",
                        symbol: "checkmark.seal",
                        tone: .amber
                    )
                    Spacer()
                    InversionStatusBadge("AWAITING VERIFICATION", tone: .amber)
                }
                InversionDivider()
                InversionKeyValueRow("driver run", value: driverRunID, monospaced: true)
                TextField("Verification note (optional)", text: $note, axis: .vertical)
                    .lineLimit(1...4)
                    .textFieldStyle(.roundedBorder)
                Text("Accept verifies that the visible provider result satisfies the requested acceptance criteria. Reject records that it does not. Neither action reruns the model.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                HStack {
                    Button("Reject Result", role: .destructive, action: reject)
                        .disabled(isBusy)
                    Spacer()
                    if isBusy { ProgressView().controlSize(.small) }
                    Button(action: accept) {
                        Label("Verify & Accept", systemImage: "checkmark.seal.fill")
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(isBusy)
                }
            }
        }
        .frame(maxWidth: 820)
    }
}

private struct ApprovalCard: View {
    let pending: CAPTPendingApproval
    let isBusy: Bool
    let approve: () -> Void
    let deny: () -> Void

    var body: some View {
        InversionPanel(tone: .amber) {
            VStack(alignment: .leading, spacing: 14) {
                HStack(alignment: .top) {
                    InversionSectionHeader(
                        "Execution approval required",
                        eyebrow: "HUMAN AUTHORITY BOUNDARY",
                        detail: "Review the exact execution identity before CAPT consumes this one-use approval.",
                        symbol: "person.crop.circle.badge.checkmark",
                        tone: .amber
                    )
                    InversionStatusBadge("awaiting approval", tone: .amber)
                }

                InversionDivider()

                Text(pending.objective)
                    .font(.body.weight(.medium))
                    .lineLimit(4)
                    .textSelection(.enabled)

                HStack(spacing: 8) {
                    InversionMetric("provider", value: pending.provider, symbol: "cpu", tone: .cyan)
                    InversionMetric("model", value: pending.model, symbol: "cube")
                    if !pending.skillNames.isEmpty {
                        InversionMetric(
                            "skills",
                            value: "\(pending.skillNames.count)",
                            symbol: "puzzlepiece.extension",
                            tone: .cyan
                        )
                    }
                }

                InversionKeyValueRow("request", value: pending.requestID, monospaced: true)
                InversionKeyValueRow(
                    "prompt digest",
                    value: pending.promptAssemblyDigest,
                    tone: .cyan,
                    monospaced: true
                )
                if !pending.skillNames.isEmpty {
                    InversionKeyValueRow("skills", value: pending.skillNames.joined(separator: " · "))
                }
                if let proposalID = pending.proposalID {
                    InversionKeyValueRow(
                        "proposal",
                        value: proposalID + " · " + (pending.selectedPromptKind ?? "selected"),
                        monospaced: true
                    )
                }
                if let expiresAt = pending.expiresAt {
                    InversionKeyValueRow(
                        "expires",
                        value: expiresAt.formatted(date: .omitted, time: .standard),
                        tone: .amber
                    )
                }

                HStack {
                    Button("Deny", role: .destructive, action: deny)
                        .disabled(isBusy || !pending.isActionable())
                    Spacer()
                    Button(action: approve) {
                        Label("Approve & Run", systemImage: "play.fill")
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(isBusy || !pending.isActionable())
                }
            }
        }
        .frame(maxWidth: 820)
    }
}

private struct ComposerView: View {
    @Binding var draft: String
    @Binding var promptIntelligence: String
    @Binding var reasoningEffort: String
    @Binding var remotePromptCompilationAllowed: Bool
    let remotePromptCompilationAvailable: Bool
    let showRemotePromptCompilationControl: Bool
    let enabled: Bool
    let skillMode: String
    let highRiskAuthority: Bool
    let send: () -> Void

    private let modes = ["AUTO", "OFF", "OMNI", "META", "FORGE", "SIGMA"]
    private let reasoningModes = ["", "none", "minimal", "low", "medium", "high", "xhigh"]

    var body: some View {
        VStack(spacing: 0) {
            HStack(alignment: .bottom, spacing: 10) {
                VStack(alignment: .leading, spacing: 8) {
                    HStack(spacing: 8) {
                        Image(systemName: "brain.head.profile")
                            .foregroundStyle(InversionTone.violet.color)
                        Picker("Prompt Intelligence", selection: $promptIntelligence) {
                            ForEach(modes, id: \.self) { Text($0).tag($0) }
                        }
                        .labelsHidden()
                        .pickerStyle(.menu)
                        .frame(width: 102)
                        .disabled(!enabled)

                        HStack(spacing: 5) {
                            Image(systemName: "dial.high")
                                .foregroundStyle(InversionTone.cyan.color)
                            Picker("Reasoning", selection: $reasoningEffort) {
                                ForEach(reasoningModes, id: \.self) { mode in
                                    Text(mode.isEmpty ? "DEFAULT" : mode.uppercased()).tag(mode)
                                }
                            }
                            .labelsHidden()
                            .pickerStyle(.menu)
                            .frame(width: 96)
                            .disabled(!enabled)
                        }
                        .help("Reasoning effort frozen into the proposal, HumanApproval, and provider dispatch")

                        if showRemotePromptCompilationControl {
                            Toggle("REMOTE PI", isOn: $remotePromptCompilationAllowed)
                                .toggleStyle(.switch)
                                .controlSize(.mini)
                                .disabled(!enabled || !remotePromptCompilationAvailable)
                                .help("Allow Prompt Intelligence to use the selected remote model")
                        }

                        Text(promptIntelligence == "AUTO"
                             ? "CAPT selects the governed stage chain from the task."
                             : "Explicit stage mode is recorded in proposal provenance.")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .lineLimit(1)

                        Spacer(minLength: 8)

                        InversionStatusBadge(
                            skillMode == "off" ? "skills off" : "skills " + skillMode,
                            tone: skillMode == "off" ? .neutral : .cyan
                        )
                        if highRiskAuthority {
                            InversionStatusBadge("elevated authority", tone: .amber)
                        }
                    }

                    if showRemotePromptCompilationControl &&
                        promptIntelligence != "OFF" &&
                        !remotePromptCompilationAllowed {
                        Label(
                            remotePromptCompilationAvailable
                                ? "Remote Prompt Intelligence is off. Enable REMOTE PI to enhance with the selected cloud model."
                                : "Remote Prompt Intelligence is blocked because Provider Network is Local only.",
                            systemImage: "brain.head.profile"
                        )
                        .font(.caption)
                        .foregroundStyle(InversionTone.amber.color)
                    }

                    HStack(alignment: .bottom, spacing: 10) {
                        TextField("Message CAPT…", text: $draft, axis: .vertical)
                            .lineLimit(1...8)
                            .textFieldStyle(.plain)
                            .font(.body)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 10)
                            .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                            .overlay {
                                RoundedRectangle(cornerRadius: 12, style: .continuous)
                                    .strokeBorder(
                                        draft.isEmpty
                                            ? Color.primary.opacity(0.08)
                                            : InversionTone.amber.color.opacity(0.26),
                                        lineWidth: 1
                                    )
                            }

                        Button(action: send) {
                            Image(systemName: "arrow.up")
                                .font(.system(size: 13, weight: .bold))
                                .frame(width: 30, height: 30)
                        }
                        .buttonStyle(.borderedProminent)
                        .keyboardShortcut(.return, modifiers: [.command])
                        .disabled(!enabled || draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                        .help("Send (⌘↩)")
                    }
                }
            }
            .padding(.horizontal, 18)
            .padding(.vertical, 13)
            .background(.regularMaterial)
        }
    }
}
