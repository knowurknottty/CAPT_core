import SwiftUI
import CAPTCoreDesktop

private enum MissionScope: String, CaseIterable, Identifiable {
    case missionGrade = "Mission-grade"
    case active = "Executing"
    case all = "All activity"
    var id: String { rawValue }
}

struct MissionBrowserView: View {
    @ObservedObject var store: CAPTOperatorStore
    @State private var selectedID: String?
    @State private var scope: MissionScope = .missionGrade
    @State private var cancelTaskID: String?
    @State private var cancelRunID: String?

    var body: some View {
        HSplitView {
            VStack(spacing: 0) {
                scopePicker
                Divider()
                missionList
            }
            .frame(minWidth: 340, idealWidth: 420)

            missionDetail
        }
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
        VStack(alignment: .leading, spacing: 8) {
            Picker("Mission scope", selection: $scope) {
                ForEach(MissionScope.allCases) { item in Text(item.rawValue).tag(item) }
            }
            .pickerStyle(.segmented)
            Text(scopeHelp)
                .font(.caption)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(12)
    }

    @ViewBuilder
    private var missionList: some View {
        if visibleMissions.isEmpty {
            EmptyMissionState(
                title: "No \(scope.rawValue.lowercased()) missions",
                systemImage: "scope",
                detail: scope == .missionGrade
                    ? "Mission-grade shows requests with multiple governed tasks. One-turn chat activity remains available under All activity."
                    : "No missions currently match this filter."
            )
        } else {
            List(visibleMissions, selection: $selectedID) { mission in
                MissionRow(mission: mission).tag(mission.id)
            }
        }
    }

    @ViewBuilder
    private var missionDetail: some View {
        if let mission = selectedMission {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    missionHeader(mission)
                    taskTree(mission)
                }
                .padding(24)
                .frame(maxWidth: .infinity, alignment: .topLeading)
            }
            .textSelection(.enabled)
        } else {
            EmptyMissionState(
                title: "Select a mission",
                systemImage: "point.3.connected.trianglepath.dotted",
                detail: "Inspect the governed mission, every task, its status, and any attached DriverRun."
            )
        }
    }

    private func missionHeader(_ mission: CAPTMissionSummary) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline) {
                Text(mission.title).font(.title2.bold())
                Spacer()
                StateBadge(mission.missionState)
            }
            Text(mission.id).font(.caption.monospaced()).foregroundStyle(.secondary)
            HStack(spacing: 16) {
                Label("\(mission.taskCount) task\(mission.taskCount == 1 ? "" : "s")", systemImage: "checklist")
                Label("\(mission.completedTaskCount)/\(mission.taskCount) terminal", systemImage: "chart.bar.fill")
            }
            .font(.callout)
            .foregroundStyle(.secondary)
            if mission.taskCount > 0 {
                ProgressView(value: Double(mission.completedTaskCount), total: Double(mission.taskCount))
            }
        }
        .padding(16)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    private func taskTree(_ mission: CAPTMissionSummary) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Tasks").font(.headline)
            ForEach(Array(mission.tasks.enumerated()), id: \.element.id) { index, task in
                TaskCard(
                    ordinal: index + 1,
                    task: task,
                    run: store.driverRuns.first { $0.taskID == task.id },
                    canCancelTask: canCancel(task),
                    canCancelRun: canCancelRun(for: task),
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
        switch scope {
        case .missionGrade:
            return store.missions.filter(\.isMultiTask)
        case .active:
            return store.missions.filter(\.hasActiveExecution)
        case .all:
            return store.missions
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
        case .missionGrade: return "Longer work only: missions with multiple governed tasks."
        case .active: return "Tasks that are ready, assigned, running, or suspended right now."
        case .all: return "Complete runtime history, including one-turn chat activity and legacy drafts."
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
        VStack(alignment: .leading, spacing: 6) {
            Text(mission.title).font(.headline).lineLimit(2)
            HStack(spacing: 8) {
                StateBadge(mission.missionState)
                Text("\(mission.taskCount) tasks")
                Text("·")
                Text("\(mission.completedTaskCount)/\(mission.taskCount) terminal")
                Spacer()
            }
            .font(.caption)
            .foregroundStyle(.secondary)
            Text(shortID(mission.id))
                .font(.caption2.monospaced())
                .foregroundStyle(.tertiary)
        }
        .padding(.vertical, 5)
    }

    private func shortID(_ value: String) -> String {
        value.count > 18 ? String(value.suffix(18)) : value
    }
}

private struct TaskCard: View {
    let ordinal: Int
    let task: CAPTTaskSummary
    let run: CAPTDriverRunSummary?
    let canCancelTask: Bool
    let canCancelRun: Bool
    let cancelTask: () -> Void
    let cancelRun: () -> Void
    @State private var expanded = true

    var body: some View {
        DisclosureGroup(isExpanded: $expanded) {
            VStack(alignment: .leading, spacing: 9) {
                LabeledContent("Task ID", value: task.id).font(.caption.monospaced())
                if let driver = task.assignedDriverID {
                    LabeledContent("Assigned driver", value: driver)
                }
                LabeledContent("Attempt", value: "\(task.attempt) / \(task.maxAttempts)")
                if !task.dependencies.isEmpty {
                    LabeledContent("Depends on", value: task.dependencies.joined(separator: ", "))
                        .font(.caption)
                }
                if let run {
                    Divider()
                    HStack {
                        Label(run.driverID, systemImage: "bolt.horizontal.circle")
                        StateBadge(run.state)
                        Spacer()
                        Text(run.reconciliationStatus)
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    Text(run.id).font(.caption2.monospaced()).foregroundStyle(.secondary)
                }
                if canCancelTask || canCancelRun {
                    HStack {
                        if canCancelTask { Button("Cancel Task", role: .destructive, action: cancelTask) }
                        if canCancelRun { Button("Cancel DriverRun", role: .destructive, action: cancelRun) }
                    }
                }
            }
            .padding(.top, 8)
        } label: {
            HStack(alignment: .top, spacing: 10) {
                Text(String(format: "%02d", ordinal))
                    .font(.caption.monospaced().bold())
                    .foregroundStyle(.secondary)
                VStack(alignment: .leading, spacing: 4) {
                    Text(task.title).font(.body.weight(.semibold))
                    HStack(spacing: 8) {
                        StateBadge(task.state)
                        if task.consequential {
                            Label("consequential", systemImage: "exclamationmark.triangle")
                                .font(.caption2).foregroundStyle(.secondary)
                        }
                    }
                }
                Spacer()
            }
        }
        .padding(14)
        .background(.quaternary.opacity(0.55), in: RoundedRectangle(cornerRadius: 14, style: .continuous))
    }
}

private struct StateBadge: View {
    let state: String
    init(_ state: String) { self.state = state }

    var body: some View {
        Text(state.replacingOccurrences(of: "_", with: " ").uppercased())
            .font(.caption2.weight(.semibold))
            .padding(.horizontal, 7)
            .padding(.vertical, 3)
            .background(.quaternary, in: Capsule())
    }
}

private struct EmptyMissionState: View {
    let title: String
    let systemImage: String
    let detail: String

    var body: some View {
        VStack(spacing: 10) {
            Image(systemName: systemImage).font(.system(size: 30)).foregroundStyle(.secondary)
            Text(title).font(.headline)
            Text(detail)
                .font(.callout)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 420)
        }
        .padding(24)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
