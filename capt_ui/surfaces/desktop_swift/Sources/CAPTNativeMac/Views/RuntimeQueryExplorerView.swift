import SwiftUI
import CAPTCoreDesktop

/// Schema-light forensic read surface. Only live-advertised QUERY operations
/// can be invoked. This never constructs a RuntimeService command envelope.
struct RuntimeQueryExplorerView: View {
    @ObservedObject var store: CAPTOperatorStore
    @State private var operation = "identity"
    @State private var payloadJSON = "{}"

    var body: some View {
        VStack(alignment: .leading, spacing: 9) {
            Text("Runtime Query Explorer").font(.headline)
            Text("All live RuntimeService read operations are inspectable here. Mutations and model execution require their own governed control surfaces.")
                .font(.caption).foregroundStyle(.secondary)

            HStack {
                Picker("Read operation", selection: $operation) {
                    ForEach(store.runtimeCapabilities?.queryOperations ?? [], id: \.self) {
                        Text($0).tag($0)
                    }
                }
                .accessibilityIdentifier("runtime-query-operation")
                .frame(maxWidth: 330)
                Button("Execute read-only query") {
                    store.performReadOnlyRuntimeQuery(
                        operation, payloadJSON: payloadJSON
                    )
                }
                .buttonStyle(.borderedProminent)
                .disabled(
                    store.connectionState != .connected ||
                    store.runtimeQueryBusy ||
                    store.runtimeCapabilities?.supportsQuery(operation) != true
                )
            }

            Text("Optional query arguments · JSON object")
                .font(.caption.bold()).foregroundStyle(.secondary)
            TextEditor(text: $payloadJSON)
                .font(.caption.monospaced())
                .frame(minHeight: 70, maxHeight: 90)
                .overlay(RoundedRectangle(cornerRadius: 8)
                    .strokeBorder(Color.primary.opacity(0.12)))
                .accessibilityIdentifier("runtime-query-payload")

            if store.runtimeQueryBusy {
                ProgressView("Reading authoritative runtime state…")
            }
            if let error = store.runtimeQueryError {
                Text(error).font(.caption).foregroundStyle(.red).textSelection(.enabled)
            }
            if !store.runtimeQueryOutput.isEmpty {
                Text("Authoritative query response (bounded preview)")
                    .font(.caption.bold()).foregroundStyle(.secondary)
                ScrollView {
                    Text(store.runtimeQueryOutput)
                        .font(.caption2.monospaced())
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .topLeading)
                }
                .frame(maxHeight: 250)
                .padding(8)
                .background(.quaternary, in: RoundedRectangle(cornerRadius: 8))
                .accessibilityIdentifier("runtime-query-response")
            }
        }
        .padding(14)
        .background(.quaternary, in: RoundedRectangle(cornerRadius: 12))
    }
}
