import SwiftUI
import CAPTCoreDesktop

private enum MissionScope: String, CaseIterable, Identifiable {
    case attention = "Needs action"
    case active = "Marked running"
    case missionGrade = "Multi-task"
    case all = "All history"
    var id: String { rawValue }
}

struct MissionBrowserView: View {
    @ObservedObject var store: CAPTOperatorStore
    @Binding var selection: CAPTSidebarSection
    @State private var selectedID: String?
    @State private var scope: MissionScope = .attention
    @State private var searchText = ""
    @State private var cancelTaskID: String?
    @State private var cancelRunID: String?

    var body: some View {
        HSplitView {
            VStack(spacing: 0) {
                scopePicker
                InversionDivider()
                missionList
            }
            .frame(minWidth: 270, idealWidth: 300, maxWidth: 330)

            missionDetail
                .frame(minWidth: 430)
        }
        .navigationTitle("Missions")
        .onAppear { store.refreshHistory() }
        .confirmationDialog("Cancel this governed task?", isPresented: Binding(
            get: { cancelTaskID != nil }, set: { if !$0 { cancelTaskID = nil } }
        )) {
            if let id = cancelTaskID {
                Button("Cancel Task", role: .destructive) {
                    store.cancelTask(id); cancelTaskID = nil
                }
            }
            Button("Keep Running", role: .cancel) { cancelTaskID = nil }
        }
        .confirmationDialog("Cancel this DriverRun?", isPresented: Binding(
            get: { cancelRunID != nil }, set: { if !$0 { cancelRunID = nil } }
        )) {
            if let id = cancelRunID {
                Button("Cancel DriverRun", role: .destructive) {
                    store.cancelDriverRun(id); cancelRunID = nil
                }
            }
            Button("Keep Running", role: .cancel) { cancelRunID = nil }
        }
    }

    private var scopePicker: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("WORK QUEUE")
                        .font(.caption2.weight(.semibold))
                        .tracking(1.2)
                        .foregroundStyle(InversionTone.cyan.color)
                    Text("Unfinished work, with an honest status")
                        .font(.callout.weight(.semibold))
                }
                Spacer()
                InversionStatusBadge("\(visibleMissions.count) visible", tone: .cyan, monospaced: true)
            }

            Picker("Mission scope", selection: $scope) {
                ForEach(MissionScope.allCases) { item in Text(item.rawValue).tag(item) }
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .controlSize(.small)

            TextField("Search missions, task descriptions, or IDs", text: $searchText)
                .textFieldStyle(.roundedBorder)
                .accessibilityIdentifier("mission-search")
            HStack {
                Text("\(store.missions.count) recorded · \(store.missions.filter { CAPTMissionTriage.classify($0).needsHumanAttention }.count) need review or recovery")
                    .font(.caption2).foregroundStyle(.secondary)
                Spacer()
                Button("Refresh") { store.refreshHistory() }.controlSize(.small)
            }
            Text(scopeHelp)
                .font(.caption)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(14)
        .background(.ultraThinMaterial)
    }

    @ViewBuilder
    private var missionList: some View {
        if visibleMissions.isEmpty {
            EmptyMissionState(
                title: "No \(scope.rawValue.lowercased()) missions",
                systemImage: "scope",
                detail: "No matching items. Change the filter or clear search to inspect the complete historical ledger."
            )
        } else {
            List(visibleMissions, selection: $selectedID) { mission in
                MissionRow(mission: mission)
                    .tag(mission.id)
                    .listRowSeparator(.hidden)
                    .listRowBackground(Color.clear)
            }
            .listStyle(.inset)
        }
    }

    @ViewBuilder
    private var missionDetail: some View {
        if let mission = selectedMission {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    missionHeader(mission)
                    missionNextAction(mission)
                    taskTree(mission)
                }
                .padding(InversionVisualLanguage.pagePadding)
                .frame(maxWidth: 920)
                .frame(maxWidth: .infinity, alignment: .topLeading)
            }
            .textSelection(.enabled)
        } else {
            EmptyMissionState(
                title: "Select a mission",
                systemImage: "point.3.connected.trianglepath.dotted",
                detail: "Inspect the mission graph, every governed task, execution state, and attached DriverRun."
            )
        }
    }

    private func missionHeader(_ mission: CAPTMissionSummary) -> some View {
        let tone = InversionVisualLanguage.tone(forState: mission.missionState)
        return InversionPanel(tone: tone, padding: 20) {
            VStack(alignment: .leading, spacing: 14) {
                HStack(alignment: .top) {
                    InversionSectionHeader(
                        CAPTMissionTriage.readableTitle(mission.title, maxLength: 150),
                        eyebrow: "MISSION",
                        detail: mission.id,
                        symbol: "scope",
                        tone: tone
                    )
                    InversionStatusBadge(CAPTMissionTriage.classify(mission).rawValue, tone: tone)
                }

                HStack(spacing: 9) {
                    InversionMetric(
                        "tasks",
                        value: "\(mission.taskCount)",
                        symbol: "checklist",
                        tone: .cyan
                    )
                    InversionMetric(
                        "succeeded",
                        value: "\(mission.succeededTaskCount)/\(mission.taskCount)",
                        symbol: "checkmark.seal.fill",
                        tone: mission.succeededTaskCount == mission.taskCount && mission.taskCount > 0
                            ? .success : .cyan
                    )
                    InversionMetric(
                        "failed / cancelled",
                        value: "\(mission.failedTaskCount) / \(mission.cancelledTaskCount)",
                        symbol: "exclamationmark.triangle.fill",
                        tone: mission.failedTaskCount > 0 ? .danger
                            : (mission.cancelledTaskCount > 0 ? .amber : .neutral)
                    )
                    InversionMetric(
                        "running marker",
                        value: mission.hasActiveExecution ? "1+ tasks" : "none",
                        symbol: "waveform.path.ecg",
                        tone: mission.hasActiveExecution ? .cyan : .neutral
                    )
                }

                if mission.taskCount > 0 {
                    ProgressView(
                        value: Double(mission.succeededTaskCount),
                        total: Double(mission.taskCount)
                    )
                    .tint(InversionTone.success.color)
                }
            }
        }
    }

    private func missionNextAction(_ mission: CAPTMissionSummary) -> some View {
        let triage = CAPTMissionTriage.classify(mission)
        return InversionPanel(tone: .cyan, padding: 15) {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("WHAT'S ACTUALLY HAPPENING")
                        .font(.caption.bold()).foregroundStyle(.secondary)
                    Spacer()
                    InversionStatusBadge(triage.rawValue)
                }
                Text(triage.explanation).font(.callout)
                Text("Next: " + triage.nextStep)
                    .font(.callout.weight(.medium))
                HStack {
                    Button("Open Kanban") { selection = .kanban }
                        .buttonStyle(.bordered)
                    Button("Prepare continuation in Chat") {
                        let cards = CAPTKanbanProjection.cards(
                            missions: [mission], runs: store.driverRuns,
                            approvals: store.approvals, council: store.activeCouncil)
                        if let card = cards.first(where: { $0.needsAttention }) ?? cards.first {
                            store.prepareKanbanContinuation(card)
                            selection = .chat
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(mission.tasks.isEmpty)
                }
                .controlSize(.small)
                Text(CAPTMissionTriage.counts(mission))
                    .font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                Text("Stored mission state: " + mission.missionState
                    + " · derived status: " + triage.rawValue
                    + " · no external worker heartbeat attested")
                    .font(.caption2).foregroundStyle(.secondary)
                let waiting = store.approvals.filter {
                    $0.missionID == mission.id && $0.isActionable()
                }
                if !waiting.isEmpty {
                    Text(String(waiting.count) + " actionable HumanApproval requests; inspect Approvals before any execution.")
                        .font(.caption).foregroundStyle(.orange)
                }
                let lost = store.driverRuns.filter {
                    $0.missionID == mission.id && $0.state == "lost"
                }
                if !lost.isEmpty {
                    Text(String(lost.count) + " lost DriverRun receipts. Do not automatically replay these providers.")
                        .font(.caption).foregroundStyle(.orange)
                }
            }
        }
    }

    private func taskTree(_ mission: CAPTMissionSummary) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            InversionSectionHeader(
                "Task graph",
                eyebrow: "EXECUTION PLAN",
                detail: "Each node is authoritative runtime state; DriverRuns remain independently inspectable.",
                symbol: "point.3.connected.trianglepath.dotted",
                tone: .cyan
            )
            .padding(.bottom, 2)

            ForEach(Array(mission.tasks.enumerated()), id: \.element.id) { index, task in
                TaskCard(
                    ordinal: index + 1,
                    isLast: index == mission.tasks.count - 1,
                    task: task,
                    run: store.driverRuns.first { $0.taskID == task.id },
                    canCancelTask: canCancel(task),
                    canCancelRun: canCancelRun(for: task),
                    inspect: {
                        let runID = store.driverRuns.first { $0.taskID == task.id }?.id
                        store.inspectMissionTask(task.id, runID: runID)
                    },
                    inspectedJSON: store.inspectedTaskID == task.id ? store.inspectedTaskJSON : nil,
                    cancelTask: { cancelTaskID = task.id },
                    cancelRun: {
                        if let run = store.driverRuns.first(where: { $0.taskID == task.id }) {
                            cancelRunID = run.id
                        }
                    }
                )
            }
        }
    }

    private var visibleMissions: [CAPTMissionSummary] {
        let base: [CAPTMissionSummary]
        switch scope {
        case .attention:
            base = store.missions.filter {
                let triage = CAPTMissionTriage.classify($0)
                return ($0.isMultiTask && triage.needsHumanAttention) || $0.hasActiveExecution
            }
        case .missionGrade: base = store.missions.filter(\.isMultiTask)
        case .active: base = store.missions.filter(\.hasActiveExecution)
        case .all: base = store.missions
        }
        let filtered = base.filter { mission in
            searchText.isEmpty || mission.id.localizedCaseInsensitiveContains(searchText) ||
            mission.title.localizedCaseInsensitiveContains(searchText) ||
            mission.tasks.contains { $0.title.localizedCaseInsensitiveContains(searchText) }
        }
        return filtered.sorted {
            let a = CAPTMissionTriage.classify($0).priority
            let b = CAPTMissionTriage.classify($1).priority
            return a == b ? $0.id < $1.id : a < b
        }
    }

    private var selectedMission: CAPTMissionSummary? {
        if let selectedID, let exact = visibleMissions.first(where: { $0.id == selectedID }) {
            return exact
        }
        return visibleMissions.first
    }

    private var scopeHelp: String {
        switch scope {
        case .attention:
            return "Interrupted runs, unverified results, and failed work. Stored 'executing' alone does not mean a worker is alive."
        case .missionGrade:
            return "Every multi-task mission, including completed and interrupted history."
        case .active:
            return "Tasks stored as running (external worker heartbeat has NOT been checked)."
        case .all:
            return "Complete mission history, including one-turn chat sessions and old drafts."
        }
    }

    private func canCancel(_ task: CAPTTaskSummary) -> Bool {
        !task.isTerminal && store.runtimeCapabilities?.supportsCommand("cancel_task") == true
    }

    private func canCancelRun(for task: CAPTTaskSummary) -> Bool {
        guard let run = store.driverRuns.first(where: { $0.taskID == task.id }) else { return false }
        return ["created", "submitted", "running", "suspended"].contains(run.state) &&
            store.runtimeCapabilities?.supportsCommand("cancel_driver_run") == true
    }
}

private struct MissionRow: View {
    let mission: CAPTMissionSummary

    var body: some View {
        let triage = CAPTMissionTriage.classify(mission)
        let tone = InversionVisualLanguage.tone(forState: mission.missionState)
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top, spacing: 8) {
                Circle()
                    .fill(tone.color)
                    .frame(width: 7, height: 7)
                    .padding(.top, 5)
                Text(CAPTMissionTriage.readableTitle(mission.title, maxLength: 105))
                    .font(.callout.weight(.semibold))
                    .lineLimit(2)
                Spacer(minLength: 4)
                if mission.hasActiveExecution {
                    Image(systemName: "waveform.path.ecg")
                        .font(.caption)
                        .foregroundStyle(InversionTone.cyan.color)
                }
            }

            HStack(spacing: 7) {
                InversionStatusBadge(triage.rawValue, tone: tone)
                Text("\(mission.taskCount) tasks")
                Text("·").foregroundStyle(.tertiary)
                Text("\(mission.succeededTaskCount)/\(mission.taskCount) succeeded")
                if mission.failedTaskCount > 0 {
                    Text("·").foregroundStyle(.tertiary)
                    Text("\(mission.failedTaskCount) failed")
                        .foregroundStyle(InversionTone.danger.color)
                }
                if mission.cancelledTaskCount > 0 {
                    Text("·").foregroundStyle(.tertiary)
                    Text("\(mission.cancelledTaskCount) cancelled")
                        .foregroundStyle(InversionTone.amber.color)
                }
                Spacer()
            }
            .font(.caption)
            .foregroundStyle(.secondary)

            if mission.taskCount > 0 {
                ProgressView(
                    value: Double(mission.succeededTaskCount),
                    total: Double(mission.taskCount)
                )
                .controlSize(.mini)
                .tint(InversionTone.success.color)
            }

            Text(CAPTMissionTriage.counts(mission))
                .font(.caption2).foregroundStyle(.secondary)
                .lineLimit(2)
            Text(shortID(mission.id))
                .font(.caption2.monospaced())
                .foregroundStyle(.tertiary)
        }
        .padding(.vertical, 8)
    }

    private func shortID(_ value: String) -> String {
        value.count > 24 ? "…" + String(value.suffix(24)) : value
    }
}

private struct TaskCard: View {
    let ordinal: Int
    let isLast: Bool
    let task: CAPTTaskSummary
    let run: CAPTDriverRunSummary?
    let canCancelTask: Bool
    let canCancelRun: Bool
    let inspect: () -> Void
    let inspectedJSON: String?
    let cancelTask: () -> Void
    let cancelRun: () -> Void
    @State private var expanded = false

    var body: some View {
        HStack(alignment: .top, spacing: 13) {
            timeline
            InversionPanel(tone: tone, padding: 14) {
                DisclosureGroup(isExpanded: $expanded) {
                    VStack(alignment: .leading, spacing: 10) {
                        InversionDivider()
                        InversionKeyValueRow("task id", value: task.id, monospaced: true)
                        if let driver = task.assignedDriverID {
                            InversionKeyValueRow("assigned", value: driver)
                        }
                        InversionKeyValueRow("attempt", value: "\(task.attempt) / \(task.maxAttempts)")
                        if !task.dependencies.isEmpty {
                            InversionKeyValueRow("depends on", value: task.dependencies.joined(separator: " · "))
                        }

                        if let run {
                            InversionDivider()
                            HStack(spacing: 8) {
                                Image(systemName: "bolt.horizontal.circle")
                                    .foregroundStyle(InversionTone.cyan.color)
                                Text(run.driverID).font(.callout.weight(.medium))
                                InversionStatusBadge(run.state)
                                Spacer()
                                Text(run.reconciliationStatus)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                            Text(run.id)
                                .font(.caption2.monospaced())
                                .foregroundStyle(.tertiary)
                        }

                        Button("Inspect stored task + DriverRun state", action: inspect)
                            .buttonStyle(.bordered)
                            .help("Read authoritative aggregate state; no execution or approval")
                        if let inspectedJSON {
                            ScrollView {
                                Text(inspectedJSON).font(.caption2.monospaced())
                                    .textSelection(.enabled)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                            }
                            .frame(maxHeight: 220)
                            .padding(8)
                            .background(.quaternary, in: RoundedRectangle(cornerRadius: 8))
                        }
                        if canCancelTask || canCancelRun {
                            HStack {
                                Spacer()
                                if canCancelTask {
                                    Button("Cancel Task", role: .destructive, action: cancelTask)
                                }
                                if canCancelRun {
                                    Button("Cancel DriverRun", role: .destructive, action: cancelRun)
                                }
                            }
                        }
                    }
                    .padding(.top, 8)
                } label: {
                    HStack(alignment: .top, spacing: 10) {
                        VStack(alignment: .leading, spacing: 5) {
                            Text(CAPTMissionTriage.readableTitle(task.title, maxLength: 170))
                                .font(.body.weight(.semibold))
                            HStack(spacing: 8) {
                                InversionStatusBadge(task.state, tone: tone)
                                if task.consequential {
                                    InversionStatusBadge("consequential", tone: .amber)
                                }
                            }
                        }
                        Spacer()
                    }
                }
            }
        }
    }

    private var tone: InversionTone {
        InversionVisualLanguage.tone(forState: task.state)
    }

    private var timeline: some View {
        VStack(spacing: 0) {
            ZStack {
                Circle().fill(tone.color.opacity(0.13))
                Circle().strokeBorder(tone.color.opacity(0.42), lineWidth: 1)
                Text(String(format: "%02d", ordinal))
                    .font(.caption2.monospaced().weight(.bold))
                    .foregroundStyle(tone.color)
            }
            .frame(width: 30, height: 30)

            if !isLast {
                Rectangle()
                    .fill(Color.primary.opacity(0.10))
                    .frame(width: 1)
                    .frame(minHeight: 56)
            }
        }
    }
}

private struct EmptyMissionState: View {
    let title: String
    let systemImage: String
    let detail: String

    var body: some View {
        VStack(spacing: 12) {
            ZStack {
                Circle().fill(InversionTone.cyan.color.opacity(0.08))
                Image(systemName: systemImage)
                    .font(.system(size: 26, weight: .light))
                    .foregroundStyle(InversionTone.cyan.color)
            }
            .frame(width: 58, height: 58)
            Text(title).font(.headline)
            Text(detail)
                .font(.callout)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 440)
        }
        .padding(28)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
