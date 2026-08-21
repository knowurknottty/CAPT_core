import SwiftUI
import CAPTCoreDesktop

struct ApprovalQueueView: View {
    @ObservedObject var store: CAPTOperatorStore

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Approval Queue").font(.title2.bold())
                        Text("Decisions are authoritative. External-origin approvals are not dispatched from this screen.")
                            .font(.callout).foregroundStyle(.secondary)
                    }
                    Spacer()
                    Button("Refresh") { store.refreshHistory() }
                }
                if store.pendingApprovals.isEmpty {
                    Text("No pending approval decisions.")
                        .foregroundStyle(.secondary)
                        .padding(.top, 24)
                } else {
                    ForEach(store.pendingApprovals) { approval in
                        approvalCard(approval)
                    }
                }
            }
            .padding(24)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
    private func approvalCard(_ approval: CAPTApprovalSummary) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text(approval.operation).font(.headline)
                Text(approval.risk.uppercased()).font(.caption2.bold())
                    .foregroundStyle(approval.risk == "low" ? Color.secondary : Color.orange)
                Spacer()
                Text(approval.provider + (approval.model.isEmpty ? "" : " / " + approval.model))
                    .font(.caption).foregroundStyle(.secondary)
            }
            Text(approval.id).font(.system(.caption, design: .monospaced)).textSelection(.enabled)
            if !approval.targetRoot.isEmpty {
                Text(approval.targetRoot).font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
            }
            HStack {
                Text("Mission: \(approval.missionID)").font(.caption2).foregroundStyle(.secondary)
                Text("Uses: \(approval.remainingUses)").font(.caption2).foregroundStyle(.secondary)
                Spacer()
                Button("Deny", role: .destructive) {
                    store.decideQueuedApproval(approval, decision: "deny")
                }
                Button("Approve Decision") {
                    store.decideQueuedApproval(approval, decision: "approve")
                }
                .buttonStyle(.borderedProminent)
            }
            Text("Approval does not reconstruct or dispatch the originating execution from this queue.")
                .font(.caption2).foregroundStyle(.secondary)
        }
        .padding(14)
        .background(.quaternary, in: RoundedRectangle(cornerRadius: 12))
    }
}
