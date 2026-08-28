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
    @State private var showVerification = false
    @State private var showConsiderations = false

    private var canSelect: Bool {
        proposal.isActive && proposal.isApprovalSelectable && !isBusy
    }

    private var statusLabel: String {
        if proposal.status == "clarification_required" && proposal.isApprovalSelectable {
            return "READY FOR APPROVAL"
        }
        return proposal.status.replacingOccurrences(of: "_", with: " ").uppercased()
    }

    private var compilerLabel: String {
        let enabled = proposal.stageRecords.first(where: { $0.executionEnabled })
        guard let enabled else { return "Deterministic / no model stage executed" }
        let location = (enabled.endpointClass ?? "unknown").uppercased()
        let provider = enabled.provider ?? "unknown-provider"
        let model = enabled.model ?? "unknown-model"
        return "\(location) · \(provider) · \(model)"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            header
            stageStrip
            actions
            editSection
            promptComparison
            verificationSection
        }
        .padding(16)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 14))
        .overlay { RoundedRectangle(cornerRadius: 14).stroke(.blue.opacity(0.45)) }
        .task(id: proposal.proposalID) { editedPrompt = proposal.proposedPrompt }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            Label("Prompt Intelligence proposal", systemImage: "brain.head.profile")
                .font(.headline)
            HStack(spacing: 8) {
                Text(statusLabel)
                    .font(.caption.bold())
                Text("r\(proposal.revision)")
                    .font(.caption.monospaced())
                Text(compilerLabel)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Text("CAPT proposed this. You have not approved execution yet.")
                .font(.callout)
                .foregroundStyle(.secondary)
        }
    }

    private var stageStrip: some View {
        HStack(spacing: 6) {
            if proposal.stageChain.isEmpty {
                Text("Enhancement OFF").font(.caption.bold())
            } else {
                ForEach(Array(proposal.stageChain.enumerated()), id: \.offset) { index, stage in
                    Text(stage).font(.caption.bold()).padding(.horizontal, 7).padding(.vertical, 4)
                        .background(.quaternary, in: Capsule())
                    if index < proposal.stageChain.count - 1 {
                        Image(systemName: "arrow.right").font(.caption2).foregroundStyle(.secondary)
                    }
                }
            }
            Spacer()
        }
    }

    private var promptComparison: some View {
        DisclosureGroup("Review prompt details", isExpanded: $showPromptDetails) {
            VStack(spacing: 10) {
                GroupBox("Original — literal operator prompt") {
                    Text(proposal.originalPrompt)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .textSelection(.enabled)
                        .font(.callout)
                }
                GroupBox("CAPT proposed execution prompt") {
                    Text(proposal.proposedPrompt)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .textSelection(.enabled)
                        .font(.callout)
                }
            }
            .padding(.top, 6)
        }
        .font(.caption)
    }

    @ViewBuilder
    private var verificationSection: some View {
        if !proposal.verificationCriteria.isEmpty {
            DisclosureGroup(
                "Verification contract (\(proposal.verificationCriteria.count))",
                isExpanded: $showVerification
            ) {
                VStack(alignment: .leading, spacing: 6) {
                    ForEach(proposal.verificationCriteria, id: \.self) { item in
                        Label(item, systemImage: "checkmark.circle")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                }
                .padding(.top, 6)
            }
            .font(.caption)
        }
        if !proposal.unresolvedQuestions.isEmpty {
            let blocking = !proposal.isApprovalSelectable
            DisclosureGroup(
                blocking
                    ? "Blocking clarifications (\(proposal.unresolvedQuestions.count))"
                    : "Advisory considerations (\(proposal.unresolvedQuestions.count))",
                isExpanded: $showConsiderations
            ) {
                VStack(alignment: .leading, spacing: 6) {
                    ForEach(proposal.unresolvedQuestions, id: \.self) { item in
                        Label(item, systemImage: blocking ? "exclamationmark.circle" : "questionmark.circle")
                            .font(.caption)
                            .foregroundStyle(blocking ? Color.orange : Color.secondary)
                    }
                }
                .padding(.top, 6)
            }
            .font(.caption)
        }
    }

    @ViewBuilder
    private var editSection: some View {
        if editing {
            VStack(alignment: .leading, spacing: 6) {
                Text("Operator-edited proposal").font(.caption.bold())
                TextEditor(text: $editedPrompt)
                    .font(.body.monospaced())
                    .frame(minHeight: 120)
                    .padding(6)
                    .background(.quaternary, in: RoundedRectangle(cornerRadius: 8))
                Text("The edited bytes become the exact prompt bound into HumanApproval.")
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
    }

    private var actions: some View {
        HStack {
            Button("Cancel Proposal", role: .destructive, action: cancel)
                .disabled(isBusy)
            Spacer()
            Button(editing ? "Hide Editor" : "Edit Upgrade") { editing.toggle() }
                .disabled(!canSelect)
            Button("Use Original") { select(.original, "") }
                .disabled(!canSelect)
            if editing {
                Button("Use Edited") { select(.edited, editedPrompt) }
                    .disabled(!canSelect || editedPrompt.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
            Button("Use Upgrade") { select(.upgrade, "") }
                .buttonStyle(.borderedProminent)
                .disabled(!canSelect || !proposal.hasMaterialUpgrade)
        }
    }
}
