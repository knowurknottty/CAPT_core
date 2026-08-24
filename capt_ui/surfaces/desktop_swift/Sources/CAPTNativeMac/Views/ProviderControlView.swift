import SwiftUI
import CAPTCoreDesktop

struct ProviderControlView: View {
    @ObservedObject var store: CAPTOperatorStore
    @State private var credentialReference = ""
    @State private var apiKey = ""
    @State private var showAdvancedCredentialReference = false

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
                        .disabled(store.isBusy)
                    if let action = CAPTOperatorCLI.providerActionLabel(
                        provider: item, executionProviderID: store.provider
                    ) {
                        Button(action) { store.activateProvider(item.id) }
                            .disabled(store.isBusy)
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
                .disabled(store.isBusy)
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
            Text("Provider credentials").font(.headline)
            if let item = selectedProvider {
                if item.id == "openrouter" {
                    Text("Set the OpenRouter API key once. CAPT stores it in macOS Keychain as service ‘capt-provider’, account ‘openrouter’. RuntimeService persists only keychain:openrouter.")
                        .font(.callout)
                        .foregroundStyle(.secondary)

                    HStack {
                        SecureField("OpenRouter API key", text: $apiKey)
                            .textFieldStyle(.roundedBorder)
                        Button("Set API Key") {
                            let submittedKey = apiKey
                            Task {
                                if await store.configureProviderAPIKey(
                                    providerID: item.id,
                                    apiKey: submittedKey
                                ) {
                                    apiKey = ""
                                }
                            }
                        }
                        .disabled(
                            apiKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ||
                            store.isBusy
                        )
                    }

                    if let status = store.providerCredentialStatus[item.id] {
                        Text(status)
                            .font(.caption)
                            .foregroundStyle(status.localizedCaseInsensitiveContains("failed") ? .red : .secondary)
                    }
                }

                DisclosureGroup(
                    "Advanced credential reference",
                    isExpanded: $showAdvancedCredentialReference
                ) {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            TextField(
                                "env:OPENROUTER_API_KEY or keychain:openrouter",
                                text: $credentialReference
                            )
                            .textFieldStyle(.roundedBorder)

                            Button("Save Reference") {
                                let submittedReference = credentialReference
                                Task {
                                    if await store.setProviderKeyReference(
                                        providerID: item.id,
                                        reference: submittedReference
                                    ) {
                                        credentialReference = ""
                                    }
                                }
                            }
                            .disabled(
                                credentialReference.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ||
                                store.isBusy
                            )
                        }
                        Text("Stored reference: \(item.keyRef). Raw keys are rejected here; use Set API Key above for OpenRouter.")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    .padding(.top, 6)
                }
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
