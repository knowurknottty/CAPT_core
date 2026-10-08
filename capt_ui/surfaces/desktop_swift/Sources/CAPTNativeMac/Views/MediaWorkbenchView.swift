import SwiftUI
import CAPTCoreDesktop

/// One-chat, human-governed media pipeline. Never uploads without a separate
/// exact HumanApproval followed by an explicit Run action.
struct MediaWorkbenchView: View {
    @ObservedObject var store: CAPTOperatorStore
    @Binding var draft: String
    @State private var selectedAdapter = ""
    @State private var maxCostUSD = "1.00"

    private var route: CAPTMediaRouteDescriptor? {
        store.mediaRoutes.first(where: { $0.adapterID == selectedAdapter })
    }

    private var budget: Double? {
        let parsed = Double(maxCostUSD)
        return parsed.flatMap { $0.isFinite && $0 >= 0 ? $0 : nil }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 11) {
            HStack {
                Label("Governed Media I/O", systemImage: "photo.on.rectangle.angled")
                    .font(.subheadline.weight(.semibold))
                Spacer()
                Text("local quarantine → HumanApproval → provider")
                    .font(.caption2).foregroundStyle(.secondary)
            }

            if store.mediaRoutes.isEmpty {
                Text("No validated provider/model media routes are configured. Files remain private and local. Configure exact media routes before generating or uploading.")
                    .font(.caption)
                    .foregroundStyle(.orange)
                Button("Refresh model capabilities") { store.refreshMediaRoutes() }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
            } else {
                Picker("Provider, model and modality", selection: $selectedAdapter) {
                    Text("Choose media route").tag("")
                    ForEach(store.mediaRoutes) { option in
                        Text(option.displayName).tag(option.adapterID)
                    }
                }
                .accessibilityIdentifier("media-provider-route")

                if let route {
                    HStack {
                        Label(route.transport, systemImage: "network")
                        Text(route.mediaTypes.joined(separator: ", "))
                    }
                    .font(.caption2).foregroundStyle(.secondary)
                    HStack {
                        Text("Maximum authorized cost (USD)")
                        TextField("USD", text: $maxCostUSD)
                            .textFieldStyle(.roundedBorder)
                            .frame(width: 95)
                            .accessibilityIdentifier("media-cost-limit")
                        Text("Configured route ceiling: $" +
                             String(format: "%.2f", route.maximumPriceUSD))
                            .foregroundStyle(.secondary)
                    }
                    .font(.caption)
                    if !route.supports(store.activeChatAttachments) {
                        Text("Selected route cannot consume this attachment set. Input routes require compatible staged files and the approved inline size limit; generation routes require no input files.")
                            .font(.caption).foregroundStyle(.orange)
                    }
                }
            }

            if let requestID = store.activeMediaApprovalID {
                Text("Approval: " + requestID)
                    .font(.caption2.monospaced())
                    .textSelection(.enabled)
                HStack {
                    Text("HumanApproval: " + (store.mediaApprovalState.isEmpty ?
                                             "check pending" : store.mediaApprovalState))
                    if !store.mediaResultState.isEmpty {
                        Text("Job: " + store.mediaResultState)
                    }
                    Spacer()
                    Button("Refresh status") { store.refreshMediaWorkflow() }
                        .disabled(store.mediaWorkflowBusy)
                        .buttonStyle(.bordered)
                    if store.mediaApprovalState == "requested" {
                        Button("Approve exact media request") { store.approveMediaRequest() }
                            .disabled(store.mediaWorkflowBusy)
                            .buttonStyle(.borderedProminent)
                    }
                    if store.mediaApprovalState == "approved" {
                        Button("Run approved media") { store.runApprovedMedia() }
                            .disabled(store.mediaWorkflowBusy)
                            .buttonStyle(.borderedProminent)
                    }
                }
                .font(.caption)
                if store.mediaResultState == "submitted" ||
                   store.mediaResultState == "processing" {
                    Button("Poll existing video job") { store.advanceMediaJob(download: false) }
                        .disabled(store.mediaWorkflowBusy)
                        .buttonStyle(.bordered)
                }
                if store.mediaResultState == "ready_to_download" {
                    Button("Download approved video artifact") {
                        store.advanceMediaJob(download: true)
                    }
                    .disabled(store.mediaWorkflowBusy)
                    .buttonStyle(.bordered)
                }
            } else {
                Button("Prepare governed media approval") {
                    if let route, let budget {
                        store.prepareMediaApproval(
                            route: route, prompt: draft, maxCostUSD: budget)
                    }
                }
                .disabled(store.mediaWorkflowBusy || route == nil ||
                          !(route?.supports(store.activeChatAttachments) ?? false) ||
                          budget == nil || draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ||
                          (budget ?? 0) < (route?.maximumPriceUSD ?? 0) ||
                          store.authoritySettings.providerNetwork != .remoteAllowed)
                .buttonStyle(.borderedProminent)
                .accessibilityIdentifier("media-prepare-approval")
            }

            if store.mediaWorkflowBusy {
                ProgressView().controlSize(.small)
            }
            if !store.mediaWorkflowMessage.isEmpty {
                Text(store.mediaWorkflowMessage)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .textSelection(.enabled)
            }
            Text("Files remain quarantined until one human-approved model request. Model results are unverified candidates. No automatic retries or charges.")
                .font(.caption2).foregroundStyle(.secondary)
        }
        .padding(13)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))
        .onAppear {
            store.refreshMediaRoutes()
            if store.activeMediaApprovalID != nil { store.refreshMediaWorkflow() }
        }
        .onChange(of: store.mediaRoutes) { routes in
            if selectedAdapter.isEmpty { selectedAdapter = routes.first?.adapterID ?? "" }
        }
        .onChange(of: store.activeSessionID) { _ in
            if store.activeMediaApprovalID != nil { store.refreshMediaWorkflow() }
        }
    }
}
