import SwiftUI
import CAPTCoreDesktop

struct RuntimeControlView: View {
    @ObservedObject var store: CAPTOperatorStore
    @State private var confirmResume = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Runtime & Recovery").font(.title2.bold())
                    Text("Governed checkpoint and resume operations routed through RuntimeService.")
                        .font(.callout).foregroundStyle(.secondary)
                }
                HStack {
                    Button("Create Checkpoint") { store.createCheckpoint() }
                        .buttonStyle(.borderedProminent)
                    Button("Resume Runtime") { confirmResume = true }
                        .buttonStyle(.bordered)
                }
                .disabled(store.connectionState != .connected || store.isBusy)
                if !store.runtimeControlMessage.isEmpty {
                    Text(store.runtimeControlMessage).font(.callout).foregroundStyle(.secondary)
                }
                checkpointCard
            }
            .padding(24)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .confirmationDialog("Resume the governed runtime?", isPresented: $confirmResume) {
            Button("Resume Runtime") { store.resumeRuntime() }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("CAPT will execute the authoritative resume operation and reconcile checkpoint state.")
        }
    }
    @ViewBuilder
    private var checkpointCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Latest checkpoint").font(.headline)
            if let checkpoint = store.checkpointSnapshot {
                Grid(alignment: .leading, horizontalSpacing: 18, verticalSpacing: 8) {
                    GridRow { Text("ID").foregroundStyle(.secondary); Text(checkpoint.checkpointID) }
                    GridRow { Text("Status").foregroundStyle(.secondary); Text(checkpoint.status) }
                    GridRow { Text("Created").foregroundStyle(.secondary); Text(checkpoint.createdAt) }
                    GridRow { Text("Ledger sequence").foregroundStyle(.secondary); Text("\(checkpoint.ledgerSequence)") }
                    GridRow { Text("Ledger digest").foregroundStyle(.secondary); Text(checkpoint.ledgerDigest).font(.system(.caption, design: .monospaced)) }
                    GridRow { Text("Integrity digest").foregroundStyle(.secondary); Text(checkpoint.integrityDigest).font(.system(.caption, design: .monospaced)) }
                }
                .textSelection(.enabled)
            } else {
                Text("Create a checkpoint to capture the current governed runtime position.")
                    .foregroundStyle(.secondary)
            }
        }
        .padding(14)
        .background(.quaternary, in: RoundedRectangle(cornerRadius: 12))
    }
}
