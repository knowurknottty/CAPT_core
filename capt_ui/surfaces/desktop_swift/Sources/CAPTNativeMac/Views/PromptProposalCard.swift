import SwiftUI
import CAPTCoreDesktop

struct PromptProposalCard: View {
    let proposal: CAPTPromptProposal
    let isBusy: Bool
    let select: (CAPTPromptSelection, String) -> Void
    let cancel: () -> Void

    @State private var editing = false
    @State private var editedPrompt = ""
    @State private var showPromptDetails = false
    @State private var showVerification = true
    @State private var showConsiderations = true

    private var canSelect: Bool {
        proposal.isActive && proposal.isApprovalSelectable && !isBusy
    }

    private var statusLabel: String {
        if proposal.status == "clarification_required" && proposal.isApprovalSelectable {
            return "READY FOR APPROVAL"
        }
        return proposal.status.replacingOccurrences(of: "_", with: " ").uppercased()
    }

    private var statusTone: InversionTone {
        if proposal.status == "compiler_unavailable" { return .warning }
        if !proposal.isApprovalSelectable { return .warning }
        return proposal.hasMaterialUpgrade ? .violet : .cyan
    }

    private var headerDetail: String {
        if proposal.status == "compiler_unavailable" {
            return "Prompt Intelligence could not run. The literal operator prompt remains selectable, and no execution authority has been consumed."
        }
        if proposal.stageChain.isEmpty || !proposal.hasMaterialUpgrade {
            return "CAPT has prepared a reviewable proposal without changing the operator prompt. No execution authority has been consumed."
        }
        return "CAPT has transformed the operator request, but no execution authority has been consumed. Choose the exact prompt bytes that should become the HumanApproval basis."
    }

    private var compilerLabel: String {
        let enabled = proposal.stageRecords.first(where: { $0.executionEnabled })
        guard let enabled else {
            if proposal.status == "compiler_unavailable",
               let diagnostic = proposal.unresolvedQuestions.first,
               !diagnostic.isEmpty {
                return diagnostic
            }
            return "deterministic · no model stage"
        }
        let location = (enabled.endpointClass ?? "unknown").lowercased()
        let provider = enabled.provider ?? "unknown-provider"
        let model = enabled.model ?? "unknown-model"
        return "\(location) · \(provider) · \(model)"
    }

    private var executedStageCount: Int {
        proposal.stageRecords.filter(\.executionEnabled).count
    }

    var body: some View {
        InversionPanel(tone: statusTone) {
            VStack(alignment: .leading, spacing: 16) {
                header
                stagePipeline
                actionBoundary
                if editing { editSection }
                if showPromptDetails { promptComparison }
                verificationSection
            }
        }
        .task(id: proposal.proposalID) { editedPrompt = proposal.proposedPrompt }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top, spacing: 12) {
                InversionSectionHeader(
                    "Prompt Intelligence proposal",
                    eyebrow: "PRE-EXECUTION",
                    detail: headerDetail,
                    symbol: "brain.head.profile",
                    tone: statusTone
                )
                Spacer(minLength: 8)
                InversionStatusBadge(statusLabel, tone: statusTone)
            }

            HStack(spacing: 10) {
                InversionMetric("revision", value: "r\(proposal.revision)", symbol: "arrow.triangle.2.circlepath", tone: .violet)
                InversionMetric("stages run", value: "\(executedStageCount)", symbol: "point.3.connected.trianglepath.dotted", tone: .cyan)
                InversionMetric("verification", value: "\(proposal.verificationCriteria.count)", symbol: "checkmark.seal", tone: .success)
                InversionMetric("questions", value: "\(proposal.unresolvedQuestions.count)", symbol: "questionmark.circle", tone: proposal.unresolvedQuestions.isEmpty ? .neutral : .amber)
                Spacer(minLength: 0)
            }

            InversionKeyValueRow("compiler", value: compilerLabel, tone: .cyan, monospaced: true)
            InversionKeyValueRow("proposal", value: proposal.proposalID, monospaced: true)
            if !proposal.rationale.isEmpty {
                Text(proposal.rationale)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    private var stagePipeline: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("PROMPT PIPELINE")
                .font(.caption2.weight(.semibold))
                .tracking(1.0)
                .foregroundStyle(.secondary)

            if proposal.stageChain.isEmpty {
                HStack(spacing: 8) {
                    InversionStatusBadge("ENHANCEMENT OFF", tone: .neutral)
                    Text("Literal operator prompt is the proposal basis.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            } else {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 6) {
                        ForEach(Array(proposal.stageChain.enumerated()), id: \.offset) { index, stage in
                            stageNode(stage)
                            if index < proposal.stageChain.count - 1 {
                                Image(systemName: "chevron.right")
                                    .font(.caption2.weight(.semibold))
                                    .foregroundStyle(.tertiary)
                            }
                        }
                    }
                }
            }
        }
    }

    private func stageNode(_ stage: String) -> some View {
        let record = proposal.stageRecords.first { $0.stage.caseInsensitiveCompare(stage) == .orderedSame }
        let executed = record?.executionEnabled ?? false
        return HStack(spacing: 6) {
            Circle()
                .fill(executed ? InversionTone.cyan.color : Color.secondary.opacity(0.45))
                .frame(width: 6, height: 6)
            Text(stage.uppercased())
                .font(.caption2.monospaced().weight(.semibold))
            if executed {
                Text("RUN")
                    .font(.system(size: 8, weight: .bold, design: .monospaced))
                    .foregroundStyle(InversionTone.cyan.color)
            }
        }
        .padding(.horizontal, 9)
        .padding(.vertical, 6)
        .background((executed ? InversionTone.cyan.color : Color.primary).opacity(executed ? 0.09 : 0.035), in: Capsule())
        .overlay {
            Capsule().strokeBorder((executed ? InversionTone.cyan.color : Color.primary).opacity(executed ? 0.22 : 0.08), lineWidth: 1)
        }
        .help(record?.rationale.isEmpty == false ? record!.rationale : (executed ? "Executed prompt stage" : "Stage present but not executed"))
    }

    private var actionBoundary: some View {
        VStack(alignment: .leading, spacing: 10) {
            InversionDivider()
            HStack(spacing: 8) {
                Label("SELECT APPROVAL BASIS", systemImage: "signature")
                    .font(.caption2.weight(.semibold))
                    .tracking(0.9)
                    .foregroundStyle(statusTone.color)
                Spacer()
                Button(showPromptDetails ? "Hide Comparison" : "Compare Prompts") {
                    withAnimation(.easeInOut(duration: 0.18)) { showPromptDetails.toggle() }
                }
                .controlSize(.small)
            }

            HStack {
                Button("Cancel Proposal", role: .destructive, action: cancel)
                    .disabled(isBusy)
                Spacer()
                Button(editing ? "Close Editor" : "Edit Upgrade") {
                    withAnimation(.easeInOut(duration: 0.18)) { editing.toggle() }
                }
                .disabled(!canSelect)
                Button("Use Original") { select(.original, "") }
                    .disabled(!canSelect)
                if editing {
                    Button("Use Edited") { select(.edited, editedPrompt) }
                        .disabled(!canSelect || editedPrompt.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
                Button {
                    select(.upgrade, "")
                } label: {
                    Label("Use CAPT Upgrade", systemImage: "sparkles")
                }
                .buttonStyle(.borderedProminent)
                .disabled(!canSelect || !proposal.hasMaterialUpgrade)
            }
        }
    }

    private var editSection: some View {
        InversionPanel(tone: .amber, padding: 13) {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("OPERATOR-EDITED BASIS")
                        .font(.caption2.weight(.semibold))
                        .tracking(1.0)
                        .foregroundStyle(InversionTone.amber.color)
                    Spacer()
                    Text("exact bytes")
                        .font(.caption2.monospaced())
                        .foregroundStyle(.secondary)
                }
                TextEditor(text: $editedPrompt)
                    .font(.body.monospaced())
                    .frame(minHeight: 140)
                    .padding(7)
                    .background(Color.primary.opacity(0.035), in: RoundedRectangle(cornerRadius: 9))
                    .overlay {
                        RoundedRectangle(cornerRadius: 9)
                            .strokeBorder(Color.primary.opacity(0.10), lineWidth: 1)
                    }
                Text("If selected, these edited bytes—not the displayed upgrade—become the exact prompt bound into HumanApproval.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }

    private var promptComparison: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("PROMPT COMPARISON")
                .font(.caption2.weight(.semibold))
                .tracking(1.0)
                .foregroundStyle(.secondary)

            HStack(alignment: .top, spacing: 10) {
                promptPane(
                    label: "ORIGINAL",
                    digest: proposal.originalPromptDigest,
                    text: proposal.originalPrompt,
                    tone: .neutral
                )
                promptPane(
                    label: "CAPT UPGRADE",
                    digest: proposal.proposedPromptDigest,
                    text: proposal.proposedPrompt,
                    tone: .violet
                )
            }
        }
    }

    private func promptPane(label: String, digest: String, text: String, tone: InversionTone) -> some View {
        InversionPanel(tone: tone, padding: 12) {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text(label)
                        .font(.caption2.weight(.semibold))
                        .tracking(0.9)
                        .foregroundStyle(tone == .neutral ? Color.secondary : tone.color)
                    Spacer()
                    Text(shortDigest(digest))
                        .font(.caption2.monospaced())
                        .foregroundStyle(.tertiary)
                }
                ScrollView {
                    Text(text)
                        .font(.callout)
                        .frame(maxWidth: .infinity, alignment: .topLeading)
                        .textSelection(.enabled)
                }
                .frame(minHeight: 110, maxHeight: 230)
            }
        }
        .frame(maxWidth: .infinity)
    }

    @ViewBuilder
    private var verificationSection: some View {
        if !proposal.verificationCriteria.isEmpty || !proposal.unresolvedQuestions.isEmpty {
            VStack(spacing: 8) {
                if !proposal.verificationCriteria.isEmpty {
                    DisclosureGroup(
                        isExpanded: $showVerification,
                        content: {
                            VStack(alignment: .leading, spacing: 7) {
                                ForEach(proposal.verificationCriteria, id: \.self) { item in
                                    HStack(alignment: .top, spacing: 8) {
                                        Image(systemName: "checkmark.circle")
                                            .foregroundStyle(InversionTone.success.color)
                                        Text(item)
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                    }
                                }
                            }
                            .padding(.top, 8)
                        },
                        label: {
                            HStack {
                                Text("VERIFICATION CONTRACT")
                                    .font(.caption2.weight(.semibold))
                                    .tracking(0.9)
                                Spacer()
                                InversionStatusBadge("\(proposal.verificationCriteria.count)", tone: .success, monospaced: true)
                            }
                        }
                    )
                }

                if !proposal.unresolvedQuestions.isEmpty {
                    let blocking = !proposal.isApprovalSelectable
                    DisclosureGroup(
                        isExpanded: $showConsiderations,
                        content: {
                            VStack(alignment: .leading, spacing: 7) {
                                ForEach(proposal.unresolvedQuestions, id: \.self) { item in
                                    HStack(alignment: .top, spacing: 8) {
                                        Image(systemName: blocking ? "exclamationmark.circle" : "questionmark.circle")
                                            .foregroundStyle(blocking ? InversionTone.warning.color : InversionTone.amber.color)
                                        Text(item)
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                    }
                                }
                            }
                            .padding(.top, 8)
                        },
                        label: {
                            HStack {
                                Text(blocking ? "BLOCKING CLARIFICATIONS" : "ADVISORY CONSIDERATIONS")
                                    .font(.caption2.weight(.semibold))
                                    .tracking(0.9)
                                Spacer()
                                InversionStatusBadge(
                                    "\(proposal.unresolvedQuestions.count)",
                                    tone: blocking ? .warning : .amber,
                                    monospaced: true
                                )
                            }
                        }
                    )
                }
            }
        }
    }

    private func shortDigest(_ digest: String) -> String {
        if digest.count <= 18 { return digest }
        return String(digest.prefix(11)) + "…" + String(digest.suffix(6))
    }
}
