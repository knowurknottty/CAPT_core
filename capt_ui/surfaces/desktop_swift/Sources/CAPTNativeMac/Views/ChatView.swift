import SwiftUI
import CAPTCoreDesktop

struct ChatView: View {
    @ObservedObject var store: CAPTOperatorStore
    @State private var draft = ""

    var body: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: 14) {
                        ForEach(store.messages) { message in
                            MessageRow(message: message)
                                .id(message.id)
                        }
                        if let pending = store.pendingApproval {
                            ApprovalCard(
                                pending: pending,
                                isBusy: store.isBusy,
                                approve: store.approvePending,
                                deny: store.denyPending
                            )
                            .id("pending-approval")
                        }
                    }
                    .padding(24)
                }
                .onChange(of: store.messages.count) { _ in
                    if let id = store.messages.last?.id {
                        withAnimation { proxy.scrollTo(id, anchor: .bottom) }
                    }
                }
            }
            Divider()
            ComposerView(
                draft: $draft,
                enabled: store.connectionState == .connected &&
                    store.pendingApproval == nil && !store.isBusy
            ) {
                let text = draft
                draft = ""
                store.submitPrompt(text)
            }
        }
        .navigationTitle(store.activeSessionTitle)
    }
}

private struct MessageRow: View {
    let message: CAPTChatMessage

    var body: some View {
        HStack {
            if message.role == .user { Spacer(minLength: 80) }
            VStack(alignment: .leading, spacing: 7) {
                HStack(spacing: 8) {
                    Text(message.role.rawValue.capitalized)
                        .font(.caption.bold())
                        .foregroundStyle(.secondary)
                    if let state = message.authorityState {
                        Text(state.replacingOccurrences(of: "_", with: " "))
                            .font(.caption2)
                            .padding(.horizontal, 7)
                            .padding(.vertical, 3)
                            .background(.quaternary, in: Capsule())
                    }
                }
                Text(message.text)
                    .textSelection(.enabled)
                    .font(.body)
            }
            .padding(13)
            .background(
                message.role == .user ? AnyShapeStyle(Color.accentColor.opacity(0.15)) : AnyShapeStyle(.thinMaterial),
                in: RoundedRectangle(cornerRadius: 14, style: .continuous)
            )
            if message.role != .user { Spacer(minLength: 80) }
        }
    }
}

private struct ApprovalCard: View {
    let pending: CAPTPendingApproval
    let isBusy: Bool
    let approve: () -> Void
    let deny: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("Execution approval required", systemImage: "person.crop.circle.badge.checkmark")
                .font(.headline)
            Text("\(pending.provider) · \(pending.model)")
                .font(.subheadline)
            Text(pending.objective)
                .lineLimit(3)
                .foregroundStyle(.secondary)
            LabeledContent("Request", value: pending.requestID)
                .font(.caption.monospaced())
            LabeledContent("Prompt digest", value: pending.promptAssemblyDigest)
                .font(.caption2.monospaced())
                .lineLimit(1)
            HStack {
                Button("Deny", role: .destructive, action: deny)
                    .disabled(isBusy)
                Spacer()
                Button("Approve & Run", action: approve)
                    .buttonStyle(.borderedProminent)
                    .disabled(isBusy)
            }
        }
        .padding(16)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 14))
        .overlay {
            RoundedRectangle(cornerRadius: 14)
                .stroke(.orange.opacity(0.5), lineWidth: 1)
        }
    }
}

private struct ComposerView: View {
    @Binding var draft: String
    let enabled: Bool
    let send: () -> Void

    var body: some View {
        HStack(alignment: .bottom, spacing: 10) {
            TextField("Message CAPT…", text: $draft, axis: .vertical)
                .lineLimit(1...6)
                .textFieldStyle(.plain)
                .padding(10)
                .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))
            Button(action: send) {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.title2)
            }
            .buttonStyle(.plain)
            .keyboardShortcut(.return, modifiers: [.command])
            .disabled(!enabled || draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            .help("Send (⌘↩)")
        }
        .padding(14)
    }
}
