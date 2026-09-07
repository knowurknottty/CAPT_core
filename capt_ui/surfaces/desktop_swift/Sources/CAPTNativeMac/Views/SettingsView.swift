import AppKit
import SwiftUI
import CAPTCoreDesktop

struct SettingsView: View {
    @ObservedObject var store: CAPTOperatorStore

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                header
                filesystemSection
                executionSection
                networkSection
                provenanceSection
            }
            .padding(24)
            .frame(maxWidth: 760, alignment: .leading)
        }
        .navigationTitle("Settings")
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Execution Authority").font(.title2.bold())
            Text("These controls express operator intent. CAPT RuntimeService must bind and revalidate the resulting authority in HumanApproval before any model or tool dispatch.")
                .foregroundStyle(.secondary)
        }
    }

    private var filesystemSection: some View {
        GroupBox("Filesystem") {
            VStack(alignment: .leading, spacing: 14) {
                Picker("Scope", selection: settingsBinding(\.filesystemScope)) {
                    Text("Project only").tag(CAPTFilesystemScopeMode.project)
                    Text("Custom folder").tag(CAPTFilesystemScopeMode.custom)
                    Text("Entire filesystem").tag(CAPTFilesystemScopeMode.full)
                }
                .pickerStyle(.radioGroup)

                if store.authoritySettings.filesystemScope == .project {
                    LabeledContent("Bound root", value: store.targetRoot)
                        .font(.callout)
                        .textSelection(.enabled)
                } else if store.authoritySettings.filesystemScope == .custom {
                    HStack {
                        Text(store.authoritySettings.customFilesystemRoot.isEmpty
                             ? "No folder selected"
                             : store.authoritySettings.customFilesystemRoot)
                            .font(.callout.monospaced())
                            .foregroundStyle(store.authoritySettings.customFilesystemRoot.isEmpty ? .secondary : .primary)
                            .textSelection(.enabled)
                        Spacer()
                        Button("Choose Folder…", action: chooseFolder)
                    }
                } else {
                    Label("Full filesystem scope binds `/`. This is a high-risk authority surface and still does not bypass per-operation ToolBroker admission.", systemImage: "exclamationmark.triangle.fill")
                        .foregroundStyle(.orange)
                        .font(.callout)
                }
            }
            .padding(.vertical, 6)
        }
    }

    private var executionSection: some View {
        GroupBox("Local Tools") {
            VStack(alignment: .leading, spacing: 12) {
                Toggle("Allow file mutation", isOn: settingsBinding(\.fileMutationAllowed))
                Text("Enables governed file.write/file.patch authority inside the selected filesystem scope. Reads and searches remain independently bounded.")
                    .font(.caption).foregroundStyle(.secondary)

                Divider()

                Toggle("Allow shell execution", isOn: settingsBinding(\.shellAccessAllowed))
                Text("Enables governed terminal.local execution with a scoped working directory. It does not grant SSH, Docker, or arbitrary out-of-scope paths.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            .padding(.vertical, 6)
        }
    }

    private var networkSection: some View {
        GroupBox("Provider Network") {
            VStack(alignment: .leading, spacing: 12) {
                Picker("Model endpoints", selection: settingsBinding(\.providerNetwork)) {
                    Text("Local providers only").tag(CAPTProviderNetworkPolicy.localOnly)
                    Text("Allow remote/cloud providers").tag(CAPTProviderNetworkPolicy.remoteAllowed)
                }
                .pickerStyle(.segmented)

                Toggle(
                    "Allow remote Prompt Intelligence compiler",
                    isOn: settingsBinding(\.remotePromptCompilationAllowed)
                )
                .disabled(store.authoritySettings.providerNetwork != .remoteAllowed)

                Text("Provider network authority controls model/compiler endpoints. It does not grant arbitrary HTTP, web scraping, or generic URL fetching; those require a separately governed network tool family.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .padding(.vertical, 6)
        }
    }

    private var provenanceSection: some View {
        GroupBox("Effective intent") {
            VStack(alignment: .leading, spacing: 7) {
                LabeledContent("Filesystem root", value: store.effectiveAuthorityFilesystemRoot ?? "INVALID — choose a custom folder")
                LabeledContent("Files", value: store.authoritySettings.fileMutationAllowed ? "read/search/write/patch" : "read/search")
                LabeledContent("Shell", value: store.authoritySettings.shellAccessAllowed ? "requested" : "off")
                LabeledContent("Provider network", value: store.authoritySettings.providerNetwork.rawValue)
                if store.authoritySettings.isHighRisk {
                    Label("This profile requests consequential authority. HumanApproval and runtime revalidation remain mandatory.", systemImage: "lock.shield")
                        .font(.caption)
                        .foregroundStyle(.orange)
                }
            }
            .font(.callout)
            .textSelection(.enabled)
            .padding(.vertical, 6)
        }
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
