import SwiftUI

struct InspectorView: View {
    @ObservedObject var store: CAPTOperatorStore

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                operatorHeader
                runtimePanel
                executionPanel
                approvalPanel
                authorityPanel
                if let error = store.lastError {
                    errorPanel(error)
                }
            }
            .padding(14)
        }
        .background(.ultraThinMaterial)
    }

    private var operatorHeader: some View {
        HStack(spacing: 10) {
            InversionBrandMark(compact: true)
            VStack(alignment: .leading, spacing: 1) {
                Text("OPERATOR INSPECTOR")
                    .font(.caption2.weight(.semibold))
                    .tracking(1.1)
                    .foregroundStyle(.secondary)
                Text("Next governed execution")
                    .font(.callout.weight(.semibold))
            }
            Spacer()
        }
        .padding(.horizontal, 2)
    }

    private var runtimePanel: some View {
        InversionPanel(tone: runtimeTone) {
            VStack(alignment: .leading, spacing: 10) {
                InversionSectionHeader(
                    "Runtime",
                    detail: store.runtimeIdentity,
                    symbol: "waveform.path.ecg",
                    tone: runtimeTone
                )
                InversionDivider()
                InversionKeyValueRow("connection", value: store.connectionLabel, tone: runtimeTone)
                InversionKeyValueRow(
                    "state root", value: store.runtimeStateDirectory,
                    tone: .cyan, monospaced: true
                )
                InversionKeyValueRow(
                    "task",
                    value: store.taskState == "—" ? "idle" : store.taskState,
                    monospaced: true
                )
                if let issue = store.runtimeCompatibilityIssue {
                    Label(issue, systemImage: "exclamationmark.triangle")
                        .font(.caption)
                        .foregroundStyle(InversionTone.danger.color)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
        }
    }

    private var executionPanel: some View {
        InversionPanel {
            VStack(alignment: .leading, spacing: 11) {
                InversionSectionHeader(
                    "Execution target",
                    detail: "These values define the next proposal/approval context.",
                    symbol: "scope"
                )

                inspectorField("PROVIDER", text: Binding(
                    get: { store.provider },
                    set: { store.setExecutionProvider($0) }
                ))
                inspectorField("MODEL", text: Binding(
                    get: { store.model },
                    set: { store.setExecutionModel($0) }
                ))
                inspectorField("TARGET ROOT", text: Binding(
                    get: { store.targetRoot },
                    set: { store.setExecutionTargetRoot($0) }
                ), monospaced: true)
            }
        }
    }

    @ViewBuilder
    private var approvalPanel: some View {
        InversionPanel(tone: store.pendingApproval == nil ? .neutral : .amber) {
            VStack(alignment: .leading, spacing: 10) {
                InversionSectionHeader(
                    "Approval",
                    detail: store.pendingApproval == nil
                        ? "No actionable HumanApproval is attached to this chat."
                        : "Exact execution identity is awaiting operator decision.",
                    symbol: "person.crop.circle.badge.checkmark",
                    tone: store.pendingApproval == nil ? .neutral : .amber
                )
                if let pending = store.pendingApproval {
                    InversionDivider()
                    InversionKeyValueRow("request", value: pending.requestID, monospaced: true)
                    InversionKeyValueRow(
                        "digest",
                        value: pending.promptAssemblyDigest,
                        tone: .cyan,
                        monospaced: true
                    )
                    if !pending.skillNames.isEmpty {
                        InversionKeyValueRow("skills", value: pending.skillNames.joined(separator: " · "))
                    }
                }
            }
        }
    }

    private var authorityPanel: some View {
        InversionPanel(tone: authorityTone) {
            VStack(alignment: .leading, spacing: 10) {
                InversionSectionHeader(
                    "Authority",
                    detail: "Settings express intent; RuntimeService still binds and revalidates exact capability authority.",
                    symbol: "lock.shield",
                    tone: authorityTone
                )
                InversionDivider()
                InversionKeyValueRow(
                    "filesystem",
                    value: store.authoritySettings.fileMutationAllowed ? "read · search · write · patch" : "read · search"
                )
                InversionKeyValueRow(
                    "shell",
                    value: store.authoritySettings.shellAccessAllowed ? "enabled" : "off",
                    tone: store.authoritySettings.shellAccessAllowed ? .amber : .neutral
                )
                InversionKeyValueRow(
                    "network",
                    value: store.authoritySettings.providerNetwork.rawValue,
                    tone: store.selectedProviderBlockedByNetworkAuthority
                        ? .danger
                        : (store.authoritySettings.providerNetwork == .remoteAllowed ? .amber : .neutral)
                )
                if store.selectedProviderBlockedByNetworkAuthority {
                    Label(
                        "Selected provider is remote but this profile permits local endpoints only.",
                        systemImage: "network.slash"
                    )
                    .font(.caption)
                    .foregroundStyle(InversionTone.danger.color)
                    .fixedSize(horizontal: false, vertical: true)
                }
            }
        }
    }

    private func errorPanel(_ error: String) -> some View {
        InversionPanel(tone: .danger) {
            VStack(alignment: .leading, spacing: 8) {
                InversionSectionHeader(
                    "Last error",
                    symbol: "exclamationmark.triangle",
                    tone: .danger
                )
                Text(error)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .textSelection(.enabled)
            }
        }
    }

    private var authorityTone: InversionTone {
        if store.selectedProviderBlockedByNetworkAuthority { return .danger }
        return store.authoritySettings.isHighRisk ? .amber : .cyan
    }

    private var runtimeTone: InversionTone {
        switch store.connectionState {
        case .connected: return .success
        case .connecting: return .amber
        case .failed: return .danger
        case .disconnected: return .neutral
        }
    }

    private func inspectorField(
        _ label: String,
        text: Binding<String>,
        monospaced: Bool = false
    ) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(label)
                .font(.caption2.weight(.semibold))
                .tracking(0.9)
                .foregroundStyle(.secondary)
            TextField(label.capitalized, text: text)
                .textFieldStyle(.plain)
                .font(monospaced ? .caption.monospaced() : .callout)
                .padding(.horizontal, 9)
                .padding(.vertical, 7)
                .background(Color.primary.opacity(0.045), in: RoundedRectangle(cornerRadius: 8))
                .overlay {
                    RoundedRectangle(cornerRadius: 8)
                        .strokeBorder(Color.primary.opacity(0.08), lineWidth: 1)
                }
        }
    }
}
