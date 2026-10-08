import SwiftUI
import CAPTCoreDesktop

private enum EvidenceScope: String, CaseIterable, Identifiable {
    case verified = "Verified"
    case pending = "Pending review"
    case all = "All evidence"
    var id: String { rawValue }
}

struct EvidenceBrowserView: View {
    @ObservedObject var store: CAPTOperatorStore
    @State private var scope: EvidenceScope = .verified

    private var visibleEvidence: [CAPTEvidenceSummary] {
        switch scope {
        case .verified:
            return store.evidenceItems.filter { $0.promotionState.lowercased() == "accepted" }
        case .pending:
            return store.evidenceItems.filter { $0.promotionState.lowercased() != "accepted" }
        case .all:
            return store.evidenceItems
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            Picker("Evidence status", selection: $scope) {
                ForEach(EvidenceScope.allCases) { item in Text(item.rawValue).tag(item) }
            }
            .pickerStyle(.segmented)
            .padding(.horizontal, 18).padding(.top, 12)
            Text("\(visibleEvidence.count) shown · \(store.evidenceItems.count) total · unverified claims remain preserved")
                .font(.caption).foregroundStyle(.secondary).padding(.vertical, 6)
            List(visibleEvidence) { item in
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text(item.statement).font(.headline).lineLimit(2)
                    Spacer()
                    Text(item.promotionState.uppercased()).font(.caption2.bold())
                        .padding(.horizontal, 7).padding(.vertical, 3)
                        .background(.quaternary, in: Capsule())
                }
                HStack(spacing: 16) {
                    Label("\(item.evidenceCount) evidence", systemImage: "doc.text.magnifyingglass")
                    Label(item.verificationStatus ?? "not verified", systemImage: "checkmark.seal")
                    Label(item.guardVerdict ?? "no persisted claim decision", systemImage: "shield.lefthalf.filled")
                }
                .font(.caption).foregroundStyle(.secondary)
                if let missionID = item.missionID {
                    Text(missionID).font(.caption2.monospaced()).foregroundStyle(.tertiary).textSelection(.enabled)
                }
                HStack {
                    Button("Inspect ClaimGuard + Verification") { store.reviewClaim(item) }
                        .disabled(store.runtimeCapabilities?.supportsQuery("claimguard") != true ||
                                  store.runtimeCapabilities?.supportsQuery("verification") != true)
                    Spacer()
                }
                if store.reviewedClaimID == item.id, let review = store.claimReview {
                    reviewCard(review)
                }
            }
            .padding(.vertical, 6)
        }
        .overlay {
            if visibleEvidence.isEmpty {
                VStack(spacing: 12) {
                    Image(systemName: "checkmark.seal").font(.system(size: 30))
                    Text("No claim evidence yet").font(.headline)
                    Text("Provider output appears here as evidence before verification or claim acceptance.")
                        .foregroundStyle(.secondary).multilineTextAlignment(.center)
                }
            }
        }
        .onAppear { store.refreshHistory(); store.refreshCapabilities() }
        }
    }

    private func reviewCard(_ review: CAPTClaimReviewSnapshot) -> some View {
        VStack(alignment: .leading, spacing: 7) {
            Text("Read-only epistemic review").font(.caption.bold())
            HStack {
                Label("ClaimGuard: \(review.guardVerdict)", systemImage: "shield")
                Text(review.guardAdvisory ? "ADVISORY" : "NON-ADVISORY")
                    .font(.caption2.bold()).padding(.horizontal, 6).padding(.vertical, 2)
                    .background(.quaternary, in: Capsule())
                Text(review.guardCommitted ? "COMMITTED" : "UNCOMMITTED")
                    .font(.caption2.bold()).padding(.horizontal, 6).padding(.vertical, 2)
                    .background(.quaternary, in: Capsule())
            }
            Text("Verification: \(review.verificationStatus) · trust \(review.verificationTrust)")
                .foregroundStyle(.secondary)
            Text("An advisory ClaimGuard disposition is not a persisted claim decision and does not verify the claim.")
                .font(.caption).foregroundStyle(.secondary)
        }
        .padding(10).background(.quaternary, in: RoundedRectangle(cornerRadius: 10))
    }
}
