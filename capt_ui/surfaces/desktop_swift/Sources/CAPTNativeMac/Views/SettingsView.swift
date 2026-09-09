import AppKit
import SwiftUI
import CAPTCoreDesktop

struct SettingsView: View {
    @ObservedObject var store: CAPTOperatorStore

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: InversionVisualLanguage.sectionSpacing) {
                header
                posturePanel
                filesystemSection
                executionSection
                networkSection
                effectiveIntentSection
            }
            .padding(InversionVisualLanguage.pagePadding)
            .frame(maxWidth: 900, alignment: .topLeading)
            .frame(maxWidth: .infinity, alignment: .topLeading)
        }
        .navigationTitle("Settings")
    }

    private var header: some View {
        InversionSectionHeader(
            "Execution authority",
            eyebrow: "CONTROL PLANE",
            detail: "These controls define operator intent for the next governed execution. They do not grant authority by themselves: RuntimeService freezes the normalized profile into HumanApproval and revalidates it again at dispatch.",
            symbol: "lock.shield",
            tone: authorityTone
        )
    }

    private var posturePanel: some View {
        InversionPanel(tone: authorityTone) {
            VStack(alignment: .leading, spacing: 13) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("AUTHORITY POSTURE")
                            .font(.caption2.weight(.semibold))
                            .tracking(1.1)
                            .foregroundStyle(authorityTone.color)
                        Text(store.authoritySettings.isHighRisk ? "Consequential profile requested" : "Bounded local profile")
                            .font(.title3.weight(.semibold))
                    }
                    Spacer()
                    InversionStatusBadge(
                        store.authoritySettings.isHighRisk ? "CONSEQUENTIAL" : "BOUNDED",
                        tone: authorityTone
                    )
                }

                HStack(spacing: 10) {
                    InversionMetric(
                        "filesystem",
                        value: filesystemPosture,
                        symbol: "folder.badge.gearshape",
                        tone: store.authoritySettings.filesystemScope == .full ? .amber : .cyan
                    )
                    InversionMetric(
                        "files",
                        value: store.authoritySettings.fileMutationAllowed ? "R/W" : "READ",
                        symbol: "doc.badge.gearshape",
                        tone: store.authoritySettings.fileMutationAllowed ? .amber : .cyan
                    )
                    InversionMetric(
                        "shell",
                        value: store.authoritySettings.shellAccessAllowed ? "ON" : "OFF",
                        symbol: "terminal",
                        tone: store.authoritySettings.shellAccessAllowed ? .amber : .neutral
                    )
                    InversionMetric(
                        "provider net",
                        value: store.authoritySettings.providerNetwork == .remoteAllowed ? "REMOTE" : "LOCAL",
                        symbol: "network",
                        tone: store.authoritySettings.providerNetwork == .remoteAllowed ? .amber : .cyan
                    )
                    Spacer(minLength: 0)
                }

                if store.authoritySettings.isHighRisk {
                    Label(
                        "This profile requests one or more consequential capabilities. The next proposal/approval cursor is invalidated whenever these settings change.",
                        systemImage: "exclamationmark.triangle"
                    )
                    .font(.caption)
                    .foregroundStyle(InversionTone.amber.color)
                } else {
                    Label(
                        "Default posture: project-scoped read/search, shell disabled, local provider endpoints only.",
                        systemImage: "checkmark.shield"
                    )
                    .font(.caption)
                    .foregroundStyle(.secondary)
                }
            }
        }
    }

    private var filesystemSection: some View {
        InversionPanel(tone: store.authoritySettings.filesystemScope == .full ? .amber : .cyan) {
            VStack(alignment: .leading, spacing: 14) {
                InversionSectionHeader(
                    "Filesystem boundary",
                    detail: "Select the root against which file tools and shell working-directory containment are normalized.",
                    symbol: "folder.badge.gearshape",
                    tone: store.authoritySettings.filesystemScope == .full ? .amber : .cyan
                )

                Picker("Scope", selection: settingsBinding(\.filesystemScope)) {
                    Text("Project only").tag(CAPTFilesystemScopeMode.project)
                    Text("Custom folder").tag(CAPTFilesystemScopeMode.custom)
                    Text("Entire filesystem").tag(CAPTFilesystemScopeMode.full)
                }
                .pickerStyle(.segmented)
                .frame(maxWidth: 560)

                InversionDivider()

                switch store.authoritySettings.filesystemScope {
                case .project:
                    InversionKeyValueRow("bound root", value: store.targetRoot, tone: .cyan, monospaced: true)
                    Text("The active chat target root is the filesystem authority root.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                case .custom:
                    HStack(alignment: .center, spacing: 12) {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("CUSTOM ROOT")
                                .font(.caption2.weight(.semibold))
                                .tracking(0.9)
                                .foregroundStyle(.secondary)
                            Text(store.authoritySettings.customFilesystemRoot.isEmpty ? "No folder selected" : store.authoritySettings.customFilesystemRoot)
                                .font(.caption.monospaced())
                                .foregroundStyle(store.authoritySettings.customFilesystemRoot.isEmpty ? .secondary : .primary)
                                .textSelection(.enabled)
                        }
                        Spacer()
                        Button("Choose Folder…", action: chooseFolder)
                    }
                    if store.authoritySettings.customFilesystemRoot.isEmpty {
                        Label("Incomplete authority profile: CAPT will not widen this to another directory.", systemImage: "xmark.shield")
                            .font(.caption)
                            .foregroundStyle(InversionTone.danger.color)
                    }
                case .full:
                    Label(
                        "Full filesystem binds `/`. ToolBroker admission still applies per operation, but a permitted tool can address any path visible to the CAPT process.",
                        systemImage: "exclamationmark.triangle.fill"
                    )
                    .font(.callout)
                    .foregroundStyle(InversionTone.amber.color)
                }
            }
        }
    }

    private var executionSection: some View {
        InversionPanel(tone: (store.authoritySettings.fileMutationAllowed || store.authoritySettings.shellAccessAllowed) ? .amber : .neutral) {
            VStack(alignment: .leading, spacing: 14) {
                InversionSectionHeader(
                    "Local tool authority",
                    detail: "Operation families are independently admitted. Enabling one does not imply another.",
                    symbol: "wrench.and.screwdriver",
                    tone: (store.authoritySettings.fileMutationAllowed || store.authoritySettings.shellAccessAllowed) ? .amber : .neutral
                )

                authorityToggle(
                    title: "Allow file mutation",
                    detail: "Adds file.write and file.patch to the normalized ToolBroker operation set inside the selected filesystem root.",
                    symbol: "doc.badge.gearshape",
                    isOn: settingsBinding(\.fileMutationAllowed)
                )

                InversionDivider()

                authorityToggle(
                    title: "Allow shell execution",
                    detail: "Adds terminal.exec through terminal.local with the approved filesystem scope. This does not silently grant SSH or Docker authority.",
                    symbol: "terminal",
                    isOn: settingsBinding(\.shellAccessAllowed)
                )
            }
        }
    }

    private var networkSection: some View {
        InversionPanel(tone: store.authoritySettings.providerNetwork == .remoteAllowed ? .amber : .cyan) {
            VStack(alignment: .leading, spacing: 14) {
                InversionSectionHeader(
                    "Provider network",
                    detail: "Controls which model and Prompt Intelligence endpoints may receive governed requests.",
                    symbol: "network",
                    tone: store.authoritySettings.providerNetwork == .remoteAllowed ? .amber : .cyan
                )

                Picker("Model endpoints", selection: settingsBinding(\.providerNetwork)) {
                    Text("Local providers only").tag(CAPTProviderNetworkPolicy.localOnly)
                    Text("Allow remote / cloud providers").tag(CAPTProviderNetworkPolicy.remoteAllowed)
                }
                .pickerStyle(.segmented)
                .frame(maxWidth: 560)

                InversionDivider()

                authorityToggle(
                    title: "Allow remote Prompt Intelligence compiler",
                    detail: "Permits Prompt Intelligence stages to use an approved remote compiler endpoint. Disabled automatically when provider network is local-only.",
                    symbol: "brain.head.profile",
                    isOn: settingsBinding(\.remotePromptCompilationAllowed),
                    disabled: store.authoritySettings.providerNetwork != .remoteAllowed
                )

                Label(
                    "This surface governs provider/compiler endpoints only. It does not advertise a generic HTTP or arbitrary web-fetch tool to models.",
                    systemImage: "info.circle"
                )
                .font(.caption)
                .foregroundStyle(.secondary)
            }
        }
    }

    private var effectiveIntentSection: some View {
        InversionPanel(tone: authorityTone) {
            VStack(alignment: .leading, spacing: 10) {
                InversionSectionHeader(
                    "Effective next-execution intent",
                    detail: "Human-readable projection of the profile that will be normalized and digest-bound at approval time.",
                    symbol: "signature",
                    tone: authorityTone
                )
                InversionDivider()
                InversionKeyValueRow(
                    "root",
                    value: store.effectiveAuthorityFilesystemRoot ?? "INVALID — choose a custom folder",
                    tone: store.effectiveAuthorityFilesystemRoot == nil ? .danger : .neutral,
                    monospaced: true
                )
                InversionKeyValueRow(
                    "file ops",
                    value: store.authoritySettings.fileMutationAllowed ? "file.read · file.search · file.write · file.patch" : "file.read · file.search",
                    monospaced: true
                )
                InversionKeyValueRow(
                    "shell",
                    value: store.authoritySettings.shellAccessAllowed ? "terminal.exec" : "not requested",
                    tone: store.authoritySettings.shellAccessAllowed ? .amber : .neutral,
                    monospaced: true
                )
                InversionKeyValueRow(
                    "provider",
                    value: store.authoritySettings.providerNetwork.rawValue,
                    tone: store.authoritySettings.providerNetwork == .remoteAllowed ? .amber : .cyan,
                    monospaced: true
                )
                InversionKeyValueRow(
                    "remote PI",
                    value: store.authoritySettings.remotePromptCompilationAllowed ? "allowed" : "off",
                    tone: store.authoritySettings.remotePromptCompilationAllowed ? .amber : .neutral
                )
            }
        }
    }

    private var authorityTone: InversionTone {
        store.authoritySettings.isHighRisk ? .amber : .cyan
    }

    private var filesystemPosture: String {
        switch store.authoritySettings.filesystemScope {
        case .project: return "PROJECT"
        case .custom: return "CUSTOM"
        case .full: return "FULL"
        }
    }

    private func authorityToggle(
        title: String,
        detail: String,
        symbol: String,
        isOn: Binding<Bool>,
        disabled: Bool = false
    ) -> some View {
        HStack(alignment: .top, spacing: 12) {
            ZStack {
                RoundedRectangle(cornerRadius: 9, style: .continuous)
                    .fill((isOn.wrappedValue ? InversionTone.amber : InversionTone.neutral).color.opacity(0.10))
                Image(systemName: symbol)
                    .foregroundStyle((isOn.wrappedValue ? InversionTone.amber : InversionTone.neutral).color)
            }
            .frame(width: 34, height: 34)

            VStack(alignment: .leading, spacing: 4) {
                Toggle(title, isOn: isOn)
                    .font(.body.weight(.semibold))
                    .disabled(disabled)
                Text(detail)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 0)
        }
        .opacity(disabled ? 0.55 : 1)
    }

    private func settingsBinding<Value>(_ keyPath: WritableKeyPath<CAPTExecutionAuthoritySettings, Value>) -> Binding<Value> {
        Binding(
            get: { store.authoritySettings[keyPath: keyPath] },
            set: { value in
                var updated = store.authoritySettings
                updated[keyPath: keyPath] = value
                if updated.providerNetwork == .localOnly {
                    updated.remotePromptCompilationAllowed = false
                }
                store.setAuthoritySettings(updated)
            }
        )
    }

    private func chooseFolder() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        panel.canCreateDirectories = true
        panel.prompt = "Use Folder"
        if panel.runModal() == .OK, let url = panel.url {
            var updated = store.authoritySettings
            updated.filesystemScope = .custom
            updated.customFilesystemRoot = url.path
            store.setAuthoritySettings(updated)
        }
    }
}
