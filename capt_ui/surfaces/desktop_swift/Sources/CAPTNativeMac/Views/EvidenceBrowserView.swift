import SwiftUI
import CAPTCoreDesktop

struct EvidenceBrowserView: View {
    @ObservedObject var store: CAPTOperatorStore

    var body: some View {
        List(store.evidenceItems) { item in
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
            if store.evidenceItems.isEmpty {
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
