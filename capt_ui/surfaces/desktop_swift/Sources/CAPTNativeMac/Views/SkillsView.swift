import SwiftUI
import CAPTCoreDesktop

struct SkillsView: View {
    @ObservedObject var store: CAPTOperatorStore
    @Binding var selection: CAPTSidebarSection
    @State private var search = ""
    @State private var showingCreateSheet = false

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
        .sheet(isPresented: $showingCreateSheet) {
            SkillCreationSheet(isBusy: store.skillManagementBusy) { name, description, version, body in
                store.createManagedSkill(
                    name: name, description: description, version: version, body: body
                )
                showingCreateSheet = false
            }
        }
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
                Button(action: chooseInstallSource) {
                    Label("Install…", systemImage: "square.and.arrow.down")
                }
                .disabled(!canMutatePack)
                Button {
                    showingCreateSheet = true
                } label: {
                    Label("Create…", systemImage: "plus.square")
                }
                .disabled(!canMutatePack)
                Button {
                    store.beginGuidedSkillCreation()
                    selection = .chat
                } label: {
                    Label("Create with CAPT", systemImage: "bubble.left.and.text.bubble.right")
                }
                .disabled(store.connectionState != .connected)
                Button {
                    store.refreshSkills()
                } label: {
                    Label("Verify Pack", systemImage: "checkmark.shield")
                }
                .disabled(store.connectionState != .connected || store.skillManagementBusy)
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
                    if let trust = snapshot.trust {
                        Text(trust.replacingOccurrences(of: "_", with: " "))
                    }
                }
                .font(.caption)
                .foregroundStyle(.secondary)
                .textSelection(.enabled)
            }

            if store.skillManagementBusy {
                HStack(spacing: 8) {
                    ProgressView().controlSize(.small)
                    Text(store.skillManagementMessage)
                }
                .font(.caption)
                .foregroundStyle(.secondary)
            } else if !store.skillManagementMessage.isEmpty {
                Label(store.skillManagementMessage, systemImage: "checkmark.circle")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .textSelection(.enabled)
            }
        }
        .padding(20)
    }

    private var canMutatePack: Bool {
        store.connectionState == .connected && !store.skillManagementBusy
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
            Text("Install an Agent Skill folder, create one here, or ask CAPT to guide the authoring process. CAPT will not inject a skill until the runtime verifies the resulting pack.")
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 500)
            HStack {
                Button("Install…", action: chooseInstallSource).disabled(!canMutatePack)
                Button("Create…") { showingCreateSheet = true }.disabled(!canMutatePack)
                Button("Create with CAPT") {
                    store.beginGuidedSkillCreation()
                    selection = .chat
                }
                .disabled(store.connectionState != .connected)
            }
        }
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func chooseInstallSource() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        panel.canCreateDirectories = false
        panel.prompt = "Install Skills"
        panel.message = "Choose a folder containing SKILL.md files or .skill bundles. CAPT will verify and atomically merge the discovered skills."
        if panel.runModal() == .OK, let url = panel.url {
            store.installManagedSkill(from: url.path)
        }
    }
}

private struct SkillCreationSheet: View {
    let isBusy: Bool
    let create: (String, String, String, String) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var description = ""
    @State private var version = "1.0.0"
    @State private var instructions = ""

    private var canCreate: Bool {
        !isBusy &&
        !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
        !description.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
        !instructions.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    var bodyContent: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Create Managed Skill").font(.title2.bold())
            Text("CAPT constructs a real SKILL.md, atomically merges it into the managed pack, and verifies the new manifest before it becomes selectable.")
                .font(.callout)
                .foregroundStyle(.secondary)
            TextField("name, e.g. capt-ui-review", text: $name)
            TextField("description — when CAPT should use this skill", text: $description)
            TextField("version", text: $version)
                .frame(maxWidth: 180)
            Text("Skill instructions").font(.headline)
            TextEditor(text: $instructions)
                .font(.body.monospaced())
                .frame(minHeight: 260)
                .overlay {
                    RoundedRectangle(cornerRadius: 8)
                        .stroke(.quaternary, lineWidth: 1)
                }
            HStack {
                Button("Cancel") { dismiss() }
                Spacer()
                Button("Create & Verify") {
                    create(name, description, version, instructions)
                }
                .buttonStyle(.borderedProminent)
                .disabled(!canCreate)
            }
        }
        .padding(24)
        .frame(minWidth: 640, minHeight: 520)
    }

    var body: some View { bodyContent }
}
