import AppKit
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
            ScrollView {
                VStack(alignment: .leading, spacing: InversionVisualLanguage.sectionSpacing) {
                    header
                    if let snapshot = store.managedSkills, snapshot.installed {
                        packPanel(snapshot)
                        selectionPanel
                        skillCatalog(snapshot)
                    } else {
                        emptyState
                    }
                }
                .padding(InversionVisualLanguage.pagePadding)
                .frame(maxWidth: 980, alignment: .topLeading)
                .frame(maxWidth: .infinity, alignment: .topLeading)
            }
        }
        .navigationTitle("Skills")
        .searchable(text: $search, placement: .toolbar, prompt: "Search managed skills")
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

    private var header: some View {
        HStack(alignment: .top, spacing: 16) {
            InversionSectionHeader(
                "Skill lattice",
                eyebrow: "COGNITIVE CONTEXT",
                detail: "Verified local skill instructions can be auto-selected or explicitly frozen into HumanApproval. Pack mutation remains a separate governed operator action.",
                symbol: "puzzlepiece.extension",
                tone: .violet
            )
            Spacer(minLength: 16)
            actionCluster
        }
    }

    private var actionCluster: some View {
        HStack(spacing: 8) {
            Button(action: chooseInstallSource) {
                Label("Install", systemImage: "square.and.arrow.down")
            }
            .disabled(!canMutatePack)

            Button {
                showingCreateSheet = true
            } label: {
                Label("Create", systemImage: "plus.square")
            }
            .disabled(!canMutatePack)

            Button {
                store.beginGuidedSkillCreation()
                selection = .chat
            } label: {
                Label("Create with CAPT", systemImage: "sparkles.rectangle.stack")
            }
            .buttonStyle(.borderedProminent)
            .disabled(store.connectionState != .connected)
        }
        .controlSize(.small)
    }

    private func packPanel(_ snapshot: CAPTManagedSkillSnapshot) -> some View {
        InversionPanel(tone: .cyan) {
            VStack(alignment: .leading, spacing: 13) {
                HStack(alignment: .top) {
                    InversionSectionHeader(
                        "Managed pack",
                        detail: "Runtime-verified metadata only; instruction bodies stay behind the governed context boundary.",
                        symbol: "checkmark.shield",
                        tone: .cyan
                    )
                    Spacer()
                    InversionStatusBadge("VERIFIED", tone: .success)
                }

                HStack(spacing: 10) {
                    InversionMetric("skills", value: "\(snapshot.skills.count)", symbol: "square.stack.3d.up", tone: .cyan)
                    InversionMetric("selection", value: store.skillSelectionMode.uppercased(), symbol: "slider.horizontal.3", tone: .violet)
                    InversionMetric("trust", value: (snapshot.trust ?? "unknown").replacingOccurrences(of: "_", with: " "), symbol: "lock.shield", tone: .success)
                    Spacer(minLength: 0)
                }

                InversionDivider()
                InversionKeyValueRow("pack", value: snapshot.packName + (snapshot.packVersion.map { " · " + $0 } ?? ""), monospaced: true)
                if let digest = snapshot.manifestDigest {
                    InversionKeyValueRow("manifest", value: digest, tone: .cyan, monospaced: true)
                }

                HStack {
                    if store.skillManagementBusy {
                        ProgressView().controlSize(.small)
                        Text(store.skillManagementMessage.isEmpty ? "Updating verified pack…" : store.skillManagementMessage)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    } else if !store.skillManagementMessage.isEmpty {
                        Label(store.skillManagementMessage, systemImage: "checkmark.circle")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .textSelection(.enabled)
                    }
                    Spacer()
                    Button {
                        store.refreshSkills()
                    } label: {
                        Label("Reverify", systemImage: "arrow.clockwise")
                    }
                    .controlSize(.small)
                    .disabled(store.connectionState != .connected || store.skillManagementBusy)
                }
            }
        }
    }

    private var selectionPanel: some View {
        InversionPanel(tone: selectionTone) {
            VStack(alignment: .leading, spacing: 12) {
                HStack(alignment: .firstTextBaseline) {
                    VStack(alignment: .leading, spacing: 3) {
                        Text("EXECUTION SELECTION")
                            .font(.caption2.weight(.semibold))
                            .tracking(1.0)
                            .foregroundStyle(selectionTone.color)
                        Text(modeDescription)
                            .font(.callout)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    if store.skillSelectionMode == "manual" {
                        InversionStatusBadge("\(store.selectedSkillNames.count) selected", tone: .amber, monospaced: true)
                    }
                }

                Picker("Selection", selection: Binding(
                    get: { store.skillSelectionMode },
                    set: { store.setSkillSelectionMode($0) }
                )) {
                    Text("Auto-select").tag("auto")
                    Text("Manual bind").tag("manual")
                    Text("Disabled").tag("off")
                }
                .pickerStyle(.segmented)
                .frame(maxWidth: 460)
            }
        }
    }

    private func skillCatalog(_ snapshot: CAPTManagedSkillSnapshot) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline) {
                Text("VERIFIED SKILLS")
                    .font(.caption2.weight(.semibold))
                    .tracking(1.1)
                    .foregroundStyle(.secondary)
                Text("\(filteredSkills.count) / \(snapshot.skills.count)")
                    .font(.caption2.monospacedDigit())
                    .foregroundStyle(.tertiary)
                Spacer()
            }

            LazyVStack(spacing: 9) {
                ForEach(filteredSkills) { skill in
                    skillRow(skill)
                }
            }
        }
    }

    @ViewBuilder
    private func skillRow(_ skill: CAPTManagedSkill) -> some View {
        let isSelected = store.skillSelectionMode == "manual" && store.selectedSkillNames.contains(skill.name)
        Button {
            guard store.skillSelectionMode == "manual" else { return }
            store.toggleSkill(skill.name)
        } label: {
            HStack(alignment: .top, spacing: 13) {
                ZStack {
                    RoundedRectangle(cornerRadius: 9, style: .continuous)
                        .fill((isSelected ? InversionTone.amber : InversionTone.violet).color.opacity(isSelected ? 0.16 : 0.08))
                    Image(systemName: selectionSymbol(for: skill.name))
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle((isSelected ? InversionTone.amber : InversionTone.violet).color)
                }
                .frame(width: 34, height: 34)

                VStack(alignment: .leading, spacing: 6) {
                    HStack(spacing: 8) {
                        Text(skill.name)
                            .font(.body.weight(.semibold))
                        Text(skill.version)
                            .font(.caption2.monospaced())
                            .foregroundStyle(.tertiary)
                        if isSelected {
                            InversionStatusBadge("BOUND", tone: .amber)
                        }
                        Spacer()
                    }
                    if !skill.description.isEmpty {
                        Text(skill.description)
                            .font(.callout)
                            .foregroundStyle(.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    if !skill.triggers.isEmpty {
                        HStack(spacing: 5) {
                            ForEach(Array(skill.triggers.prefix(3)), id: \.self) { trigger in
                                Text(trigger)
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                                    .padding(.horizontal, 7)
                                    .padding(.vertical, 3)
                                    .background(Color.primary.opacity(0.04), in: Capsule())
                            }
                        }
                    }
                }
                Spacer(minLength: 0)
            }
            .padding(13)
            .contentShape(Rectangle())
            .background {
                RoundedRectangle(cornerRadius: InversionVisualLanguage.compactRadius, style: .continuous)
                    .fill(.thinMaterial)
            }
            .overlay {
                RoundedRectangle(cornerRadius: InversionVisualLanguage.compactRadius, style: .continuous)
                    .strokeBorder(
                        (isSelected ? InversionTone.amber : InversionTone.violet).color.opacity(isSelected ? 0.32 : 0.12),
                        lineWidth: 1
                    )
            }
        }
        .buttonStyle(.plain)
        .disabled(store.skillSelectionMode != "manual")
        .help(store.skillSelectionMode == "manual" ? "Toggle exact HumanApproval skill binding" : "Switch to Manual bind to choose exact skills")
    }

    private var canMutatePack: Bool {
        store.connectionState == .connected && !store.skillManagementBusy
    }

    private var selectionTone: InversionTone {
        switch store.skillSelectionMode {
        case "manual": return .amber
        case "off": return .neutral
        default: return .violet
        }
    }

    private var modeDescription: String {
        switch store.skillSelectionMode {
        case "manual": return "Only checked managed skills are frozen into the next execution approval."
        case "off": return "Managed skill context is explicitly excluded from new approvals."
        default: return "CAPT verifies the pack and ranks relevant skills against each objective."
        }
    }

    private func selectionSymbol(for name: String) -> String {
        switch store.skillSelectionMode {
        case "manual": return store.selectedSkillNames.contains(name) ? "checkmark" : "circle"
        case "off": return "minus"
        default: return "sparkles"
        }
    }

    private var emptyState: some View {
        InversionPanel(tone: .violet) {
            VStack(spacing: 14) {
                InversionBrandMark(compact: true)
                Image(systemName: "puzzlepiece.extension")
                    .font(.system(size: 30))
                    .foregroundStyle(InversionTone.violet.color)
                Text("No verified managed skill pack")
                    .font(.title3.weight(.semibold))
                Text("Install an Agent Skill folder, author one directly, or let CAPT guide the design in chat. Nothing becomes selectable until RuntimeService verifies the resulting pack.")
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: 540)
                HStack {
                    Button("Install…", action: chooseInstallSource).disabled(!canMutatePack)
                    Button("Create…") { showingCreateSheet = true }.disabled(!canMutatePack)
                    Button("Create with CAPT") {
                        store.beginGuidedSkillCreation()
                        selection = .chat
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(store.connectionState != .connected)
                }
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 28)
        }
    }

    private func chooseInstallSource() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        panel.canCreateDirectories = false
        panel.prompt = "Install Skills"
        panel.message = "Choose a folder containing SKILL.md files or .skill bundles. CAPT verifies and atomically merges discovered skills."
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
        !isBusy && !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
            !description.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
            !instructions.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            InversionSectionHeader(
                "Create managed skill",
                eyebrow: "AUTHORING BOUNDARY",
                detail: "CAPT constructs SKILL.md, atomically merges it into the managed pack, then verifies the new manifest before activation.",
                symbol: "square.and.pencil",
                tone: .violet
            )

            InversionPanel {
                VStack(alignment: .leading, spacing: 12) {
                    TextField("name, e.g. capt-ui-review", text: $name)
                    TextField("description — when CAPT should use this skill", text: $description)
                    TextField("version", text: $version)
                        .frame(maxWidth: 180)
                    InversionDivider()
                    Text("INSTRUCTIONS")
                        .font(.caption2.weight(.semibold))
                        .tracking(1)
                        .foregroundStyle(.secondary)
                    TextEditor(text: $instructions)
                        .font(.body.monospaced())
                        .frame(minHeight: 250)
                        .padding(8)
                        .background(Color.primary.opacity(0.035), in: RoundedRectangle(cornerRadius: 9))
                        .overlay {
                            RoundedRectangle(cornerRadius: 9)
                                .strokeBorder(Color.primary.opacity(0.10), lineWidth: 1)
                        }
                }
            }

            HStack {
                Button("Cancel") { dismiss() }
                Spacer()
                if isBusy { ProgressView().controlSize(.small) }
                Button("Create & Verify") {
                    create(name, description, version, instructions)
                }
                .buttonStyle(.borderedProminent)
                .disabled(!canCreate)
            }
        }
        .padding(24)
        .frame(minWidth: 660, minHeight: 540)
    }
}
