import SwiftUI
import CAPTCoreDesktop

struct MemoryContextView: View {
    @ObservedObject var store: CAPTOperatorStore

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Memory & Context").font(.title2.bold())
                        Text("Authoritative CAPT memory path and most recent governed ContextPack.")
                            .font(.callout).foregroundStyle(.secondary)
                    }
                    Spacer()
                    Button("Refresh") { store.refreshMemory() }
                }
                if let memory = store.memorySnapshot {
                    status(memory)
                    context(memory)
                } else {
                    Text("Memory state has not been loaded yet.")
                        .foregroundStyle(.secondary)
                }
            }
            .padding(24)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
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
            }
            .textSelection(.enabled)
        }
        .padding(14)
        .background(.quaternary, in: RoundedRectangle(cornerRadius: 12))
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
        .padding(14)
        .background(.quaternary, in: RoundedRectangle(cornerRadius: 12))
    }
}
