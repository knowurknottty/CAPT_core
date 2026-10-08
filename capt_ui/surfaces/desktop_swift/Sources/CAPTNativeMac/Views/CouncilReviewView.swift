import SwiftUI
import CAPTCoreDesktop

/// A council is one conversation with independently approved, attributed cohorts.
/// It is not a multiplier on inference calls: N cohorts -> N provider calls.
private struct CouncilDraftCohort: Identifiable {
    let id = UUID()
    var provider: String
    var model: String
}

struct CouncilReviewView: View {
    @ObservedObject var store: CAPTOperatorStore
    @Binding var draft: String
    @State private var expanded = false
    @State private var draftCohorts = [
        CouncilDraftCohort(provider: "openrouter", model: "deepseek/deepseek-v4.1-flash"),
        CouncilDraftCohort(provider: "openrouter", model: "xiaomi/mimo-v2.6-flash"),
    ]
    @State private var vessels = 22
    @State private var parallel = false

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            DisclosureGroup(isExpanded: $expanded) {
                if let review = store.activeCouncil {
                    preparedReview(review)
                } else {
                    setup
                }
            } label: {
                HStack {
                    Image(systemName: "person.3.sequence.fill")
                    Text("Governed Council · multi-cohort")
                        .font(.callout.weight(.semibold))
                    Spacer()
                    if let review = store.activeCouncil {
                        Text("\(review.cohorts.count) cohorts · \(review.cohorts.reduce(0) { $0 + $1.vessels }) vessels")
                            .font(.caption.monospacedDigit())
                    } else {
                        Text("Opt in · no automatic parallelism")
                            .font(.caption)
                    }
                }
            }
            if let error = store.councilError {
                Text(error).font(.caption).foregroundStyle(.red).textSelection(.enabled)
            }
        }
        .padding(12)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))
        .padding(.horizontal, 18)
        .padding(.vertical, 5)
    }

    private var setup: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("One chat objective · one shared governed mission · separate HumanApproval per cohort.")
                .font(.caption).foregroundStyle(.secondary)
            ForEach($draftCohorts) { $cohort in
                HStack {
                    TextField("Provider", text: $cohort.provider)
                        .textFieldStyle(.roundedBorder).frame(width: 110)
                    TextField("Model ID", text: $cohort.model)
                        .textFieldStyle(.roundedBorder)
                        .accessibilityIdentifier("council-model-" + cohort.id.uuidString)
                    if draftCohorts.count > 1 {
                        Button {
                            draftCohorts.removeAll { $0.id == cohort.id }
                        } label: {
                            Image(systemName: "minus.circle")
                        }
                        .accessibilityLabel("Remove cohort")
                        .help("Remove this cohort")
                    }
                }
            }
            HStack {
                Button("Add Cohort") {
                    if draftCohorts.count < 24 {
                        draftCohorts.append(CouncilDraftCohort(provider: "openrouter", model: ""))
                    }
                }
                .disabled(draftCohorts.count >= 24)
                Stepper("\(vessels) vessels each", value: $vessels, in: 1...1000)
                    .frame(maxWidth: 205)
                Toggle("Run cohorts concurrently", isOn: $parallel)
                    .toggleStyle(.checkbox)
            }
            Text("Vessels are analytical perspectives, not separate model calls. The native Council is read-only by default.")
                .font(.caption).foregroundStyle(.secondary)
            Button("Prepare governed council approvals") {
                store.prepareCouncil(
                    objective: draft,
                    configurations: draftCohorts.map { ($0.provider, $0.model) },
                    vessels: vessels,
                    concurrency: parallel ? draftCohorts.count : 1
                )
                draft = ""
                expanded = true
            }
            .disabled(
                !store.canComposeInActiveChat || store.councilBusy ||
                draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ||
                draftCohorts.contains {
                    $0.model.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ||
                    $0.provider.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                }
            )
            .buttonStyle(.borderedProminent)
            .help("Request separate runtime approvals. Does not approve or dispatch any model.")
        }
        .padding(.top, 8)
    }

    private func preparedReview(_ review: CAPTCouncilReview) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(review.missionID).font(.caption2.monospaced()).textSelection(.enabled)
            ForEach(Array(review.cohorts.enumerated()), id: \.element.id) { index, cohort in
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text("Cohort \(index + 1)").font(.callout.weight(.semibold))
                        Text(cohort.model).font(.caption).textSelection(.enabled)
                        Spacer()
                        Text("\(cohort.vessels) vessels · \(cohort.state)")
                            .font(.caption.monospacedDigit())
                    }
                    if let requestID = cohort.requestID {
                        Text(requestID).font(.caption2.monospaced()).textSelection(.enabled)
                        if let expiry = cohort.expiresAt {
                            Text("Expires: " + expiry).font(.caption2).foregroundStyle(.secondary)
                        }
                        if cohort.state == "requested" {
                            HStack {
                                Button("Approve cohort \(index + 1)") {
                                    store.decideCouncilCohort(at: index, approve: true)
                                }
                                .buttonStyle(.borderedProminent)
                                Button("Deny cohort \(index + 1)", role: .destructive) {
                                    store.decideCouncilCohort(at: index, approve: false)
                                }
                                .buttonStyle(.bordered)
                            }
                            .disabled(store.councilBusy)
                        }
                    }
                }
                .padding(8)
                .background(.quaternary, in: RoundedRectangle(cornerRadius: 8))
            }
            HStack {
                if review.cohorts.contains(where: { $0.requestID == nil }) {
                    Button("Resume approval preparation") {
                        store.prepareRemainingCouncilCohorts()
                    }
                    .disabled(store.councilBusy)
                }
                Button("Refresh authoritative approval states") { store.refreshCouncil() }
                    .disabled(store.councilBusy)
                if review.executionReceipt == nil {
                    Button("Run / reattach approved council") { store.runCouncil() }
                        .buttonStyle(.borderedProminent)
                        .disabled(store.councilBusy || !review.canRunOrReattach)
                }
            }
            if store.councilBusy { ProgressView("Runtime request in progress…") }
            if let message = review.message {
                Text(message).font(.caption).textSelection(.enabled)
            }
            if let receipt = review.executionReceipt {
                DisclosureGroup("View governed council receipt") {
                    ScrollView {
                        Text(receipt).font(.caption2.monospaced()).textSelection(.enabled)
                    }.frame(maxHeight: 180)
                }
            }
        }
        .padding(.top, 8)
    }
}
