import SwiftUI

struct InspectorView: View {
    @ObservedObject var store: CAPTOperatorStore

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                GroupBox("Runtime") {
                    VStack(alignment: .leading, spacing: 8) {
                        LabeledContent("State", value: store.connectionLabel)
                        Text(store.runtimeIdentity)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .textSelection(.enabled)
                        LabeledContent("Task", value: store.taskState)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }

                GroupBox("Next execution") {
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Provider").font(.caption).foregroundStyle(.secondary)
                        TextField(
                            "Provider",
                            text: Binding(
                                get: { store.provider },
                                set: { store.setExecutionProvider($0) }
                            )
                        )
                        Text("Model").font(.caption).foregroundStyle(.secondary)
                        TextField(
                            "Model",
                            text: Binding(
                                get: { store.model },
                                set: { store.setExecutionModel($0) }
                            )
                        )
                        Text("Target root").font(.caption).foregroundStyle(.secondary)
                        TextField(
                            "Target root",
                            text: Binding(
                                get: { store.targetRoot },
                                set: { store.setExecutionTargetRoot($0) }
                            )
                        )
                        .font(.caption.monospaced())
                    }
                }

                GroupBox("Approval") {
                    if let pending = store.pendingApproval {
                        VStack(alignment: .leading, spacing: 6) {
                            Text(pending.requestID)
                                .font(.caption.monospaced())
                                .textSelection(.enabled)
                            Text(pending.promptAssemblyDigest)
                                .font(.caption2.monospaced())
                                .foregroundStyle(.secondary)
                                .lineLimit(2)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                    } else {
                        Text("No pending approval")
                            .foregroundStyle(.secondary)
                    }
                }

                GroupBox("Authority") {
                    Text("This app is a renderer/controller. RuntimeService and EventStore remain authoritative; model output is evidence until separately verified.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }

                if let error = store.lastError {
                    GroupBox("Last error") {
                        Text(error)
                            .font(.caption)
                            .foregroundStyle(.red)
                            .textSelection(.enabled)
                    }
                }
            }
            .padding(14)
        }
        .background(.ultraThinMaterial)
    }
}
