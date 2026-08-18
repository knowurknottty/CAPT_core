import SwiftUI
import CAPTCoreDesktop

struct ProviderControlView: View {
    @ObservedObject var store: CAPTOperatorStore
    @State private var credentialReference = ""

    private var selectedProvider: CAPTProviderSnapshot? {
        store.providers.first(where: { $0.id == store.provider })
            ?? store.providers.first(where: { $0.selected })
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                header
                providersSection
                modelSection
                credentialSection
                verbositySection
            }
            .padding(24)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .navigationTitle("Providers")
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Provider & Model Control").font(.title2.bold())
            Text("Operator preferences only. Runtime approval and execution authority remain in CAPT.")
                .font(.callout).foregroundStyle(.secondary)
        }
    }
    private var providersSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Providers").font(.headline)
            ForEach(store.providers) { item in
                HStack(spacing: 12) {
                    Circle()
                        .fill(item.health == "green" ? .green : item.health == "red" ? .red : .secondary)
                        .frame(width: 9, height: 9)
                    VStack(alignment: .leading, spacing: 2) {
                        HStack {
                            Text(item.name).fontWeight(item.selected ? .semibold : .regular)
                            Text(item.kind.uppercased()).font(.caption2).foregroundStyle(.secondary)
                            if item.selected { Text("ACTIVE").font(.caption2.bold()) }
                        }
                        Text("\(item.transport) · context \(item.contextLimit)" +
                             (item.latencyMs.map { " · \($0) ms" } ?? ""))
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer()
                    Button("Test") { store.testProvider(item.id) }
                    if !item.selected {
                        Button("Activate") { store.activateProvider(item.id) }
                    }
                }
                .padding(10)
                .background(.quaternary, in: RoundedRectangle(cornerRadius: 10))
            }
        }
    }
    private var modelSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Default model").font(.headline)
            if let item = selectedProvider, !item.models.isEmpty {
                Picker("Model", selection: Binding(
                    get: { store.model },
                    set: { store.setDefaultModel($0) }
                )) {
                    ForEach(item.models, id: \.self) { model in
                        Text(model).tag(model)
                    }
                }
                .pickerStyle(.menu)
                Text("Active: \(store.modelSnapshot?.active ?? store.model)")
                    .font(.caption).foregroundStyle(.secondary)
            } else {
                Text("No discovered models for the selected provider. Test the provider to refresh inventory.")
                    .font(.callout).foregroundStyle(.secondary)
            }
        }
    }


    private var credentialSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Credential reference").font(.headline)
            if let item = selectedProvider {
                HStack {
                    TextField("env:OPENROUTER_API_KEY or keychain:openrouter", text: $credentialReference)
                        .textFieldStyle(.roundedBorder)
                    Button("Save Reference") {
                        store.setProviderKeyReference(providerID: item.id, reference: credentialReference)
                        credentialReference = ""
                    }
                    .disabled(credentialReference.isEmpty)
                }
                Text("Stored: \(item.keyRef). Raw keys are rejected; the native app persists only CAPT secret references.")
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
    }

    private var verbositySection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("CaveCAPT verbosity").font(.headline)
            Picker("Verbosity", selection: Binding(
                get: { store.verbosity },
                set: { store.setVerbosity($0) }
            )) {
                ForEach(["minimal", "normal", "detailed", "diagnostic"], id: \.self) {
                    Text($0.capitalized).tag($0)
                }
            }
            .pickerStyle(.segmented)
        }
    }
}
