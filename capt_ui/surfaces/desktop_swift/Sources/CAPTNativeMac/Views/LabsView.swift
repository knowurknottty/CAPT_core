import SwiftUI
import CAPTCoreDesktop

struct LabsView: View {
    @ObservedObject var store: CAPTOperatorStore

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                header
                if store.labEngines.isEmpty {
                    emptyState
                } else {
                    controls
                    bindingCard
                    inputCard
                    provenanceCard
                    if let receipt = store.labReceipt {
                        receiptCard(receipt)
                    }
                }
            }
            .padding(24)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .onAppear { store.refreshLabs() }
    }

    private var header: some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 5) {
                Text("Inversion Labs").font(.title2.bold())
                Text("Specialist instruments governed through CAPT RuntimeService. Engine output is evidence, not truth by module name.")
                    .font(.callout)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Button("Refresh") { store.refreshLabs() }
                .disabled(store.connectionState != .connected || store.isBusy)
        }
    }

    @ViewBuilder
    private var emptyState: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("No Lab registry advertised", systemImage: "flask")
                .font(.headline)
            Text("Connect to the Inversion Labs CAPT runtime. A core-only runtime legitimately omits the additive Lab query/command surface.")
                .foregroundStyle(.secondary)
        }
        .padding(16)
        .background(.quaternary, in: RoundedRectangle(cornerRadius: 12))
    }

    private var controls: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 16) {
                Picker("Engine", selection: Binding(
                    get: { store.selectedLabEngineID },
                    set: { store.selectLabEngine($0) }
                )) {
                    ForEach(store.labEngines) { engine in
                        Text(engine.displayName).tag(engine.id)
                    }
                }
                .frame(minWidth: 240)

                Picker("Operation", selection: Binding(
                    get: { store.selectedLabOperation },
                    set: { store.selectLabOperation($0) }
                )) {
                    ForEach(store.selectedLabEngine?.operations ?? []) { operation in
                        Text(operation.name).tag(operation.name)
                    }
                }
                .frame(minWidth: 260)
            }

            if let operation = store.selectedLabOperationSnapshot {
                HStack(spacing: 8) {
                    Text(operation.epistemicClass.uppercased())
                        .font(.caption.bold())
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(.quaternary, in: Capsule())
                    Text(operation.description)
                        .font(.callout)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .padding(16)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 14))
    }

    private var bindingCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Governed binding").font(.headline)
            Grid(alignment: .leading, horizontalSpacing: 18, verticalSpacing: 7) {
                GridRow {
                    Text("Mission").foregroundStyle(.secondary)
                    Text(store.activeMissionID ?? "No active authoritative mission")
                        .font(.system(.caption, design: .monospaced))
                        .textSelection(.enabled)
                }
                GridRow {
                    Text("Task").foregroundStyle(.secondary)
                    Text(store.activeLabTaskID ?? "No active authoritative task")
                        .font(.system(.caption, design: .monospaced))
                        .textSelection(.enabled)
                }
                GridRow {
                    Text("Runtime command").foregroundStyle(.secondary)
                    Text("run_lab_engine_advisory")
                        .font(.system(.caption, design: .monospaced))
                }
            }
            if store.activeMissionID == nil || store.activeLabTaskID == nil {
                Label("Run a governed chat turn first; Labs will not invent mission/task lineage.", systemImage: "exclamationmark.triangle")
                    .font(.callout)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(14)
        .background(.quaternary, in: RoundedRectangle(cornerRadius: 12))
    }

    private var inputCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Bounded input").font(.headline)
                Spacer()
                Button("Reset Template") {
                    store.selectLabOperation(store.selectedLabOperation)
                }
            }
            TextEditor(text: $store.labInputJSON)
                .font(.system(.body, design: .monospaced))
                .frame(minHeight: 160, idealHeight: 210)
                .padding(8)
                .background(.background, in: RoundedRectangle(cornerRadius: 10))
                .overlay {
                    RoundedRectangle(cornerRadius: 10).stroke(.quaternary)
                }
            HStack {
                if !store.labControlMessage.isEmpty {
                    Text(store.labControlMessage)
                        .font(.callout)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Button("Run Governed Advisory") { store.runSelectedLabAdvisory() }
                    .buttonStyle(.borderedProminent)
                    .disabled(!canRun)
            }
        }
        .padding(16)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 14))
    }

    private var provenanceCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Instrument provenance & limits").font(.headline)
            if let engine = store.selectedLabEngine {
                LabeledContent("Engine", value: "\(engine.id) · \(engine.engineVersion)")
                LabeledContent("Donor commit", value: engine.donorCommit)
                    .font(.caption.monospaced())
                    .textSelection(.enabled)
                LabeledContent("Filesystem", value: engine.requiresFilesystem ? "bounded read" : "not required")
                LabeledContent("Network", value: engine.requiresNetwork ? "required" : "OFF")
                ForEach(engine.sourceFiles) { source in
                    VStack(alignment: .leading, spacing: 3) {
                        Text(source.path).font(.caption.monospaced())
                        Text(source.sha256).font(.caption2.monospaced()).foregroundStyle(.secondary)
                    }
                    .textSelection(.enabled)
                }
                if !engine.limitations.isEmpty {
                    Divider()
                    ForEach(engine.limitations, id: \.self) { limit in
                        Label(limit, systemImage: "info.circle")
                            .font(.callout)
                    }
                }
            }
        }
        .padding(14)
        .background(.quaternary, in: RoundedRectangle(cornerRadius: 12))
    }

    private func receiptCard(_ receipt: CAPTLabRunReceipt) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Recorded Lab result").font(.headline)
                Spacer()
                Text(receipt.epistemicClass.uppercased())
                    .font(.caption.bold())
                    .padding(.horizontal, 8).padding(.vertical, 4)
                    .background(.quaternary, in: Capsule())
                Text(receipt.authorityLabel)
                    .font(.caption.bold())
                    .padding(.horizontal, 8).padding(.vertical, 4)
                    .background(.quaternary, in: Capsule())
            }
            Grid(alignment: .leading, horizontalSpacing: 18, verticalSpacing: 7) {
                GridRow { Text("DriverRun").foregroundStyle(.secondary); Text(receipt.driverRunID) }
                GridRow { Text("Claim").foregroundStyle(.secondary); Text(receipt.claimID) }
                GridRow { Text("Evidence").foregroundStyle(.secondary); Text(receipt.evidenceID) }
                GridRow { Text("Promotion").foregroundStyle(.secondary); Text(receipt.promotionState) }
                GridRow { Text("Verification").foregroundStyle(.secondary); Text(receipt.verificationID ?? "none") }
                GridRow { Text("Artifact digest").foregroundStyle(.secondary); Text(receipt.artifactDigest) }
                GridRow { Text("Request digest").foregroundStyle(.secondary); Text(receipt.requestDigest) }
            }
            .font(.caption.monospaced())
            .textSelection(.enabled)
            Text("CAPT authoritatively recorded these result bytes. It has not independently verified the specialist conclusion unless a verification identity is shown above.")
                .font(.callout)
                .foregroundStyle(.secondary)
        }
        .padding(16)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 14))
    }

    private var canRun: Bool {
        store.connectionState == .connected &&
        store.runtimeCapabilities?.supportsCommand("run_lab_engine_advisory") == true &&
        store.activeMissionID != nil && store.activeLabTaskID != nil &&
        store.selectedLabEngine?.available == true && !store.isBusy
    }
}
