import SwiftUI
import CAPTCoreDesktop

struct SkillsView: View {
    @ObservedObject var store: CAPTOperatorStore
    @State private var search = ""

    private var filteredSkills: [CAPTManagedSkill] {
        guard let skills = store.managedSkills?.skills else { return [] }
        let query = search.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !query.isEmpty else { return skills }
        return skills.filter {
            $0.name.lowercased().contains(query) ||
            $0.description.lowercased().contains(query) ||
            $0.triggers.joined(separator: " ").lowercased().contains(query)
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            controlHeader
            Divider()
            if let snapshot = store.managedSkills, snapshot.installed {
                List(filteredSkills) { skill in
                    skillRow(skill)
                }
                .searchable(text: $search, placement: .toolbar, prompt: "Search skills")
            } else {
                emptyState
            }
        }
        .navigationTitle("Skills")
        .onAppear { store.refreshSkills() }
    }

    private var controlHeader: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 3) {
                    Text("Governed Skill Context").font(.title3.bold())
                    Text(modeDescription)
                        .font(.callout)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Button {
                    store.refreshSkills()
                } label: {
                    Label("Verify Pack", systemImage: "checkmark.shield")
                }
            }

            Picker("Selection", selection: Binding(
                get: { store.skillSelectionMode },
                set: { store.setSkillSelectionMode($0) }
            )) {
                Text("Auto").tag("auto")
                Text("Manual").tag("manual")
                Text("Off").tag("off")
            }
            .pickerStyle(.segmented)
            .frame(maxWidth: 360)

            if let snapshot = store.managedSkills, snapshot.installed {
                HStack(spacing: 12) {
                    Label("\(snapshot.skills.count) verified", systemImage: "checkmark.seal")
                    Text(snapshot.packName + (snapshot.packVersion.map { " · " + $0 } ?? ""))
                    if let trust = snapshot.trust { Text(trust.replacingOccurrences(of: "_", with: " ")) }
                }
                .font(.caption)
                .foregroundStyle(.secondary)
                .textSelection(.enabled)
            }
        }
        .padding(20)
    }

    private var modeDescription: String {
        switch store.skillSelectionMode {
        case "manual":
            return "Only checked managed skills are frozen into the execution approval."
        case "off":
            return "Managed skill context is explicitly disabled for new approvals."
        default:
            return "CAPT verifies the pack and selects relevant skills from each objective."
        }
    }

    @ViewBuilder
    private func skillRow(_ skill: CAPTManagedSkill) -> some View {
        Button {
            guard store.skillSelectionMode == "manual" else { return }
            store.toggleSkill(skill.name)
        } label: {
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: selectionSymbol(for: skill.name))
                    .foregroundStyle(selectionStyle(for: skill.name))
                    .frame(width: 18)
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text(skill.name).font(.headline)
                        Text(skill.version).font(.caption.monospaced()).foregroundStyle(.tertiary)
                    }
                    if !skill.description.isEmpty {
                        Text(skill.description)
                            .font(.callout)
                            .foregroundStyle(.secondary)
                            .lineLimit(3)
                    }
                    if !skill.triggers.isEmpty {
                        Text(skill.triggers.prefix(3).joined(separator: " · "))
                            .font(.caption)
                            .foregroundStyle(.tertiary)
                            .lineLimit(1)
                    }
                }
                Spacer()
            }
            .contentShape(Rectangle())
            .padding(.vertical, 4)
        }
        .buttonStyle(.plain)
        .disabled(store.skillSelectionMode != "manual")
        .help(store.skillSelectionMode == "manual" ? "Toggle skill" : "Switch to Manual to choose exact skills")
    }

    private func selectionSymbol(for name: String) -> String {
        switch store.skillSelectionMode {
        case "manual": return store.selectedSkillNames.contains(name) ? "checkmark.circle.fill" : "circle"
        case "off": return "minus.circle"
        default: return "sparkles"
        }
    }

    private func selectionStyle(for name: String) -> HierarchicalShapeStyle {
        if store.skillSelectionMode == "manual" && store.selectedSkillNames.contains(name) {
            return .primary
        }
        return .secondary
    }

    private var emptyState: some View {
        VStack(spacing: 12) {
            Image(systemName: "puzzlepiece.extension")
                .font(.system(size: 34))
                .foregroundStyle(.secondary)
            Text("No verified managed skill pack").font(.headline)
            Text("CAPT will not advertise or inject skills until the runtime verifies an installed pack.")
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 440)
            Button("Verify Again") { store.refreshSkills() }
        }
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
