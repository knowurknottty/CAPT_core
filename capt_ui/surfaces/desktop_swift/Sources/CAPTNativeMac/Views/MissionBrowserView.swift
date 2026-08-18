import SwiftUI
import CAPTCoreDesktop

struct MissionBrowserView: View {
    @ObservedObject var store: CAPTOperatorStore
    @State private var selectedID: String?

    var body: some View {
        HSplitView {
            List(store.missions, selection: $selectedID) { mission in
                VStack(alignment: .leading, spacing: 4) {
                    Text(mission.title)
                        .font(.headline)
                        .lineLimit(2)
                    HStack(spacing: 8) {
                        Text(mission.taskState ?? mission.missionState)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Spacer()
                        Text(shortID(mission.id))
                            .font(.caption.monospaced())
                            .foregroundStyle(.tertiary)
                    }
                }
                .padding(.vertical, 4)
                .tag(mission.id)
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
                    Spacer()
                }
                .padding(24)
                .frame(minWidth: 360, maxWidth: .infinity, alignment: .topLeading)
            } else {
                VStack(spacing: 12) {
                    Image(systemName: "scope").font(.system(size: 30))
                    Text("Select a mission").font(.headline)
                    Text("CAPT mission and task lineage is read directly from RuntimeService.")
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .onAppear { store.refreshHistory() }
    }

    private var selectedMission: CAPTMissionSummary? {
        guard let selectedID else { return store.missions.first }
        return store.missions.first { $0.id == selectedID }
    }

    private func shortID(_ value: String) -> String {
        value.count > 12 ? String(value.suffix(12)) : value
    }
}
