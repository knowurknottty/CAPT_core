import SwiftUI
import CAPTCoreDesktop

/// Human-first projection of the shared CAPT mission/task ledger.
/// Card movement is never a direct mutation: gated RuntimeService commands
/// and explicit verification remain the only ways to change canonical state.
struct KanbanBoardView: View {
    @ObservedObject var store: CAPTOperatorStore
    @Binding var selection: CAPTSidebarSection
    @State private var search = ""
    @State private var showClosed = false
    @State private var onlyAttention = true
    @State private var inspectID: String?
    @State private var reviewCard: CAPTKanbanCard?
    @State private var cancellation: CAPTKanbanCard?

    private var allCards: [CAPTKanbanCard] {
        CAPTKanbanProjection.cards(
            missions: store.missions, runs: store.driverRuns,
            approvals: store.approvals, council: store.activeCouncil
        )
    }
    private var visibleCards: [CAPTKanbanCard] {
        allCards.filter { card in
            (showClosed || card.lane != .resolved) &&
            (!onlyAttention || card.needsAttention) &&
            (search.isEmpty || card.task.id.localizedCaseInsensitiveContains(search) ||
             card.task.title.localizedCaseInsensitiveContains(search) ||
             card.task.missionID.localizedCaseInsensitiveContains(search) ||
             card.participants.contains { $0.localizedCaseInsensitiveContains(search) })
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text("CAPT · Collaborative Kanban").font(.title2.bold())
                    Text("Human, agent, cohort and vessel contributions—only where authoritative provenance exists.")
                        .font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                Button("Refresh") { store.refreshHistory() }
                    .buttonStyle(.bordered)
            }
            HStack(spacing: 12) {
                TextField("Search task, mission, agent, or model", text: $search)
                    .textFieldStyle(.roundedBorder)
                    .accessibilityIdentifier("kanban-search")
                Toggle("Actionable", isOn: $onlyAttention)
                    .toggleStyle(.checkbox).fixedSize()
                Toggle("Closed history", isOn: $showClosed)
                    .toggleStyle(.checkbox).fixedSize()
            }
            Text("\(visibleCards.count) cards visible · \(allCards.count) total · lane labels are derived from stored task states, not execution commands")
                .font(.caption2).foregroundStyle(.secondary)
            if !store.kanbanMessage.isEmpty {
                Text(store.kanbanMessage)
                    .font(.caption).textSelection(.enabled)
            }
            if !store.runtimeControlMessage.isEmpty {
                Text(store.runtimeControlMessage)
                    .font(.caption2).foregroundStyle(.secondary)
            }
            ScrollView(.horizontal) {
                HStack(alignment: .top, spacing: 14) {
                    ForEach(CAPTKanbanLane.allCases) { lane in
                        laneColumn(lane)
                    }
                }
                .padding(.bottom, 8)
            }
            .scrollIndicators(.visible)
        }
        .padding(16)
        .navigationTitle("Kanban")
        .onAppear {
            store.refreshHistory()
            store.refreshCapabilities()
        }
        .sheet(item: $reviewCard) { card in
            KanbanReviewSheet(card: card, store: store)
                .frame(minWidth: 530, minHeight: 435)
        }
        .confirmationDialog("Cancel the authoritative task?", isPresented: Binding(
            get: { cancellation != nil },
            set: { if !$0 { cancellation = nil } }
        )) {
            if let cancellation {
                Button("Cancel " + cancellation.task.id, role: .destructive) {
                    store.cancelTask(cancellation.task.id)
                    self.cancellation = nil
                }
            }
            Button("Keep task", role: .cancel) { cancellation = nil }
        } message: {
            Text("Cancellation is a terminal EventStore transition, not just moving a card.")
        }
    }

    private func laneColumn(_ lane: CAPTKanbanLane) -> some View {
        let cards = visibleCards.filter { $0.lane == lane }
        return VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text(lane.rawValue).font(.callout.bold())
                Spacer()
                Text(String(cards.count))
                    .font(.caption.monospacedDigit()).foregroundStyle(.secondary)
            }
            Text(lane.explanation)
                .font(.caption2).foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
                .frame(minHeight: 45, alignment: .top)
            ScrollView {
                LazyVStack(spacing: 10) {
                    ForEach(cards) { card in
                        taskCard(card)
                    }
                }
                .padding(.bottom, 4)
            }
            .frame(maxHeight: .infinity)
        }
        .padding(12)
        .frame(width: 292)
        .frame(maxHeight: .infinity, alignment: .top)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 13))
        .accessibilityIdentifier("kanban-lane-" + lane.rawValue)
    }

    private func taskCard(_ card: CAPTKanbanCard) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top) {
                Text(CAPTMissionTriage.readableTitle(card.task.title, maxLength: 112))
                    .font(.callout.weight(.semibold))
                    .lineLimit(3)
                Spacer(minLength: 4)
                if card.task.consequential {
                    Image(systemName: "lock.shield").font(.caption)
                        .help("Consequential: requires governed admission")
                }
            }
            Text(card.task.id)
                .font(.caption2.monospaced()).foregroundStyle(.tertiary)
                .lineLimit(1)
                .textSelection(.enabled)
            HStack {
                Text("Stored: " + card.task.state)
                    .font(.caption2.weight(.medium))
                Spacer()
                Text("Attempt \(card.task.attempt)/\(card.task.maxAttempts)")
                    .font(.caption2.monospacedDigit()).foregroundStyle(.secondary)
            }
            ForEach(card.participants, id: \.self) { participant in
                Text(participant)
                    .font(.caption2).foregroundStyle(.secondary)
                    .lineLimit(2)
            }
            if !card.task.dependencies.isEmpty {
                Text("Depends on: " + card.task.dependencies.joined(separator: ", "))
                    .font(.caption2).foregroundStyle(.orange)
                    .lineLimit(3)
            }
            Text("Next: " + card.nextAction)
                .font(.caption)
                .fixedSize(horizontal: false, vertical: true)

            HStack(spacing: 8) {
                Button("Inspect") {
                    inspectID = card.id
                    store.inspectMissionTask(card.task.id, runID: card.run?.id)
                }
                .buttonStyle(.bordered)
                Button("Continue") {
                    store.prepareKanbanContinuation(card)
                    selection = .chat
                }
                .buttonStyle(.borderedProminent)
                .help("Draft a governed continuation in Chat; no automatic dispatch")
            }
            .controlSize(.small)

            if card.approval?.isActionable() == true {
                Button("HumanApproval") { selection = .approvals }
                    .controlSize(.small)
                    .help("Inspect exact bounded authorization before deciding")
            }
            if card.task.state == "awaiting_verification", card.run?.state == "completed" {
                Button("Review verified evidence…") {
                    inspectID = card.id
                    store.inspectMissionTask(card.id, runID: card.run?.id)
                    reviewCard = card
                }
                .controlSize(.small)
                .help("Review receipt and explicitly accept or reject; no automatic verification")
            }
            if !card.task.isTerminal,
               store.runtimeCapabilities?.supportsCommand("cancel_task") == true {
                Button("Cancel task…", role: .destructive) { cancellation = card }
                    .controlSize(.mini)
            }
            if inspectID == card.id && store.inspectedTaskID == card.id {
                DisclosureGroup("Authoritative task + run") {
                    ScrollView {
                        Text(store.inspectedTaskJSON)
                            .font(.caption2.monospaced())
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .textSelection(.enabled)
                    }
                    .frame(maxHeight: 190)
                }
            }
        }
        .padding(11)
        .background(.background.opacity(0.82), in: RoundedRectangle(cornerRadius: 10))
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("kanban-card-" + card.id)
    }
}

private struct KanbanReviewSheet: View {
    let card: CAPTKanbanCard
    @ObservedObject var store: CAPTOperatorStore
    @Environment(\.dismiss) private var dismiss
    @State private var note = ""
    @State private var acknowledgedEvidence = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Human verification").font(.title2.bold())
            Text(card.task.id).font(.caption.monospaced()).textSelection(.enabled)
            Text("Review the exact DriverRun, result artifact and supporting Evidence before making a consequential decision. Accepting does not certify the entire mission.")
                .font(.callout).foregroundStyle(.secondary)
            ScrollView {
                Text(store.inspectedTaskID == card.id
                     ? store.inspectedTaskJSON : "Loading authoritative receipt…")
                    .font(.caption2.monospaced())
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .textSelection(.enabled)
            }
            .frame(maxHeight: 175)
            .padding(8)
            .background(.quaternary, in: RoundedRectangle(cornerRadius: 8))
            TextField("Evidence-based decision note (required)", text: $note, axis: .vertical)
                .lineLimit(2...4)
                .textFieldStyle(.roundedBorder)
            Toggle("I checked the authoritative result and supporting evidence", isOn: $acknowledgedEvidence)
                .toggleStyle(.checkbox)
            HStack {
                Button("Keep pending") { dismiss() }
                Spacer()
                Button("Reject") {
                    store.reviewKanbanResult(card, decision: "reject", note: note)
                    dismiss()
                }
                .disabled(!canReview || store.kanbanBusy)
                Button("Accept") {
                    store.reviewKanbanResult(card, decision: "accept", note: note)
                    dismiss()
                }
                .buttonStyle(.borderedProminent)
                .disabled(!canReview || store.kanbanBusy)
            }
        }
        .padding(20)
    }

    private var canReview: Bool {
        acknowledgedEvidence &&
        !note.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
        store.inspectedTaskID == card.id &&
        store.inspectedTaskJSON.contains("DRIVER RUN STATE") &&
        !store.inspectedTaskJSON.contains("Runtime read failed")
    }
}
