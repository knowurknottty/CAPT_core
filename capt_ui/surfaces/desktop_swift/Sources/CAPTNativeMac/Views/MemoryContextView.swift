import SwiftUI
import CAPTCoreDesktop

struct MemoryContextView: View {
    @ObservedObject var store: CAPTOperatorStore
    @State private var retrieval = 8
    @State private var compression = 8
    @State private var checkpoint = 8
    @State private var consolidation = 8
    @State private var hardStop = 8
    @State private var modelSafe = 8

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Memory & Context").font(.title2.bold())
                        Text("Authoritative CAPT memory path, trigger policy, and latest governed ContextPack.")
                            .font(.callout).foregroundStyle(.secondary)
                    }
                    Spacer()
                    Button("Refresh") { store.refreshMemory() }
                }
                if let memory = store.memorySnapshot {
                    status(memory)
                    policyEditor(memory)
                    context(memory)
                } else {
                    Text("Memory state has not been loaded yet.").foregroundStyle(.secondary)
                }
            }
            .padding(24).frame(maxWidth: .infinity, alignment: .leading)
        }
        .onAppear { store.refreshMemory(); syncDraft() }
        .onChange(of: store.memorySnapshot?.policyVersion) { _ in syncDraft() }
    }

    private func status(_ memory: CAPTMemoryRuntimeSnapshot) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Memory policy").font(.headline)
            Grid(alignment: .leading, horizontalSpacing: 18, verticalSpacing: 8) {
                GridRow { Text("Path").foregroundStyle(.secondary); Text(memory.active ? "ACTIVE" : "INACTIVE") }
                GridRow { Text("Policy version").foregroundStyle(.secondary); Text("\(memory.policyVersion)") }
                GridRow { Text("Trigger interval").foregroundStyle(.secondary); Text("\(memory.triggerIntervalTokens) tokens") }
                GridRow { Text("Triggers").foregroundStyle(.secondary); Text("\(memory.triggerCount)") }
                GridRow { Text("Digest").foregroundStyle(.secondary); Text(memory.policyDigest).font(.system(.caption, design: .monospaced)) }
            }.textSelection(.enabled)
        }
        .padding(14).background(.quaternary, in: RoundedRectangle(cornerRadius: 12))
    }

    private func policyEditor(_ memory: CAPTMemoryRuntimeSnapshot) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Trigger thresholds").font(.headline)
                Spacer()
                Text("1 step = \(memory.triggerIntervalTokens) tokens").font(.caption).foregroundStyle(.secondary)
            }
            policyStepper("Retrieval", value: $retrieval)
            policyStepper("Compression", value: $compression)
            policyStepper("Checkpoint", value: $checkpoint)
            policyStepper("Consolidation", value: $consolidation)
            policyStepper("Hard stop", value: $hardStop)
            policyStepper("Model safe limit", value: $modelSafe)
            Text("RuntimeService validates precedence and safe-limit relationships; the app does not override policy authority.")
                .font(.caption).foregroundStyle(.secondary)
            Button("Apply Governed Policy") {
                store.updateMemoryPolicy(
                    retrieval: retrieval, compression: compression, checkpoint: checkpoint,
                    consolidation: consolidation, hardStop: hardStop, modelSafe: modelSafe
                )
            }
            .buttonStyle(.borderedProminent)
            .disabled(store.runtimeCapabilities?.supportsCommand("update_memory_trigger_policy") != true || store.isBusy)
        }
        .padding(14).background(.quaternary, in: RoundedRectangle(cornerRadius: 12))
    }

    private func policyStepper(_ title: String, value: Binding<Int>) -> some View {
        Stepper(value: value, in: 1...64) {
            LabeledContent(title, value: "\(value.wrappedValue) steps")
        }
    }

    private func context(_ memory: CAPTMemoryRuntimeSnapshot) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Latest ContextPack").font(.headline)
            if let digest = memory.lastContextPackDigest {
                Text(memory.lastContextPackID ?? "ContextPack").fontWeight(.semibold)
                Text(digest).font(.system(.caption, design: .monospaced)).textSelection(.enabled)
                Text("\(memory.selectedRecordCount) selected records · \(memory.unresolvedConflictCount) unresolved conflicts")
                    .font(.callout).foregroundStyle(.secondary)
            } else {
                Text("No ContextPack has been emitted for the selected/global memory view yet.")
                    .foregroundStyle(.secondary)
            }
        }
        .padding(14).background(.quaternary, in: RoundedRectangle(cornerRadius: 12))
    }

    private func syncDraft() {
        guard let m = store.memorySnapshot else { return }
        retrieval = m.retrievalTriggerSteps; compression = m.compressionTriggerSteps
        checkpoint = m.checkpointTriggerSteps; consolidation = m.consolidationTriggerSteps
        hardStop = m.hardStopTriggerSteps; modelSafe = m.modelSafeLimitSteps
    }
}
