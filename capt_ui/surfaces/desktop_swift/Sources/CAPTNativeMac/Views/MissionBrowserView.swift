import SwiftUI
import CAPTCoreDesktop

struct MissionBrowserView: View {
    @ObservedObject var store: CAPTOperatorStore
    @State private var selectedID: String?
    @State private var cancelTaskID: String?
    @State private var cancelRunID: String?

    var body: some View {
        HSplitView {
            List(store.missions, selection: $selectedID) { mission in
                VStack(alignment: .leading, spacing: 4) {
                    Text(mission.title).font(.headline).lineLimit(2)
                    HStack(spacing: 8) {
                        Text(mission.taskState ?? mission.missionState)
                            .font(.caption).foregroundStyle(.secondary)
                        Spacer()
                        Text(shortID(mission.id)).font(.caption.monospaced())
                            .foregroundStyle(.tertiary)
                    }
                }
                .padding(.vertical, 4).tag(mission.id)
            }
            .frame(minWidth: 330, idealWidth: 420)

            if let mission = selectedMission {
                VStack(alignment: .leading, spacing: 16) {
                    Text(mission.title).font(.title2.bold())
                    LabeledContent("Mission", value: mission.id)
                    LabeledContent("Mission state", value: mission.missionState)
                    if let taskID = mission.taskID {
                        LabeledContent("Task", value: taskID)
                    }
                    if let taskState = mission.taskState {
                        LabeledContent("Task state", value: taskState)
                    }
                    if let run = selectedDriverRun {
                        Divider()
                        Text("DriverRun").font(.headline)
                        LabeledContent("Run", value: run.id)
                        LabeledContent("Driver", value: run.driverID)
                        LabeledContent("Run state", value: run.state)
                        LabeledContent("Reconciliation", value: run.reconciliationStatus)
                    }
                    actionButtons(for: mission)
                    Spacer()
                }
                .padding(24).frame(minWidth: 360, maxWidth: .infinity, alignment: .topLeading)
                .textSelection(.enabled)
            } else {
                VStack(spacing: 12) {
                    Image(systemName: "scope").font(.system(size: 30))
                    Text("Select a mission").font(.headline)
                    Text("CAPT mission, task, and DriverRun lineage is read directly from RuntimeService.")
                        .foregroundStyle(.secondary).multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .onAppear { store.refreshHistory() }
        .confirmationDialog("Cancel this governed task?", isPresented: Binding(
            get: { cancelTaskID != nil }, set: { if !$0 { cancelTaskID = nil } }
        )) {
            if let id = cancelTaskID { Button("Cancel Task", role: .destructive) { store.cancelTask(id); cancelTaskID = nil } }
            Button("Keep Running", role: .cancel) { cancelTaskID = nil }
        }
        .confirmationDialog("Cancel this DriverRun?", isPresented: Binding(
            get: { cancelRunID != nil }, set: { if !$0 { cancelRunID = nil } }
        )) {
            if let id = cancelRunID { Button("Cancel DriverRun", role: .destructive) { store.cancelDriverRun(id); cancelRunID = nil } }
            Button("Keep Running", role: .cancel) { cancelRunID = nil }
        }
    }

    @ViewBuilder
    private func actionButtons(for mission: CAPTMissionSummary) -> some View {
        HStack {
            if let taskID = mission.taskID, let state = mission.taskState,
               !["succeeded", "failed", "cancelled"].contains(state),
               store.runtimeCapabilities?.supportsCommand("cancel_task") == true {
                Button("Cancel Task", role: .destructive) { cancelTaskID = taskID }
            }
            if let run = selectedDriverRun,
               ["created", "submitted", "running", "suspended"].contains(run.state),
               store.runtimeCapabilities?.supportsCommand("cancel_driver_run") == true {
                Button("Cancel DriverRun", role: .destructive) { cancelRunID = run.id }
            }
        }
        .disabled(store.isBusy)
    }

    private var selectedMission: CAPTMissionSummary? {
        guard let selectedID else { return store.missions.first }
        return store.missions.first { $0.id == selectedID }
    }

    private var selectedDriverRun: CAPTDriverRunSummary? {
        guard let taskID = selectedMission?.taskID else { return nil }
        return store.driverRuns.first { $0.taskID == taskID }
    }

    private func shortID(_ value: String) -> String { value.count > 12 ? String(value.suffix(12)) : value }
}
