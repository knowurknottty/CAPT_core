import SwiftUI
import CAPTCoreDesktop

struct RuntimeControlView: View {
    @ObservedObject var store: CAPTOperatorStore
    @State private var confirmResume = false
    @State private var confirmShutdown = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Runtime & Recovery").font(.title2.bold())
                    Text("Governed lifecycle controls and the exact capability surface advertised by this RuntimeService.")
                        .font(.callout).foregroundStyle(.secondary)
                }
                HStack {
                    Button("Create Checkpoint") { store.createCheckpoint() }.buttonStyle(.borderedProminent)
                    Button("Resume Runtime") { confirmResume = true }.buttonStyle(.bordered)
                    Button("Shutdown Runtime", role: .destructive) { confirmShutdown = true }.buttonStyle(.bordered)
                }
                .disabled(store.connectionState != .connected || store.isBusy)
                if !store.runtimeControlMessage.isEmpty {
                    Text(store.runtimeControlMessage).font(.callout).foregroundStyle(.secondary)
                }
                checkpointCard
                capabilityCard
            }
            .padding(24).frame(maxWidth: .infinity, alignment: .leading)
        }
        .onAppear { store.refreshCapabilities() }
        .confirmationDialog("Resume the governed runtime?", isPresented: $confirmResume) {
            Button("Resume Runtime") { store.resumeRuntime() }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("CAPT will execute the authoritative resume operation and reconcile checkpoint state.")
        }
        .confirmationDialog("Shut down RuntimeService?", isPresented: $confirmShutdown) {
            Button("Shutdown Runtime", role: .destructive) { store.shutdownRuntime() }
            Button("Keep Running", role: .cancel) {}
        } message: {
            Text("The native app remains open. Connect will bootstrap RuntimeService again through CAPT's private runtime CLI.")
        }
    }

    private var capabilityCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Live RuntimeService capabilities").font(.headline)
            if let caps = store.runtimeCapabilities {
                capabilityLine("Components", caps.activeComponents)
                capabilityLine("Queries", caps.queryOperations)
                capabilityLine("Commands", caps.commandOperations)
                capabilityLine("Lifecycle", caps.lifecycleOperations)
                Text("Low-level `create_mission` and fixed OpenHarness operations are shown here when advertised, but the native app intentionally uses the governed chat workflow instead of duplicating competing UX paths.")
                    .font(.caption).foregroundStyle(.secondary)
            } else {
                Text("Connect or refresh to query the runtime capability contract.").foregroundStyle(.secondary)
            }
        }
        .padding(14).background(.quaternary, in: RoundedRectangle(cornerRadius: 12))
    }

    private func capabilityLine(_ label: String, _ values: [String]) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(label).font(.caption.bold()).foregroundStyle(.secondary)
            Text(values.joined(separator: " · ")).font(.caption.monospaced()).textSelection(.enabled)
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
                }.textSelection(.enabled)
            } else {
                Text("Create a checkpoint to capture the current governed runtime position.").foregroundStyle(.secondary)
            }
        }
        .padding(14).background(.quaternary, in: RoundedRectangle(cornerRadius: 12))
    }
}
