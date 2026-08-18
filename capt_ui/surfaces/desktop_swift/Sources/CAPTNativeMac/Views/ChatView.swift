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

                        if store.activeChatFlow.phase == .requestingApproval {
                            ChatProgressCard(
                                title: "Preparing governed approval",
                                detail: "CAPT is binding the prompt, provider, model, target, context and approval request."
                            )
                            .id("chat-requesting-approval")
                        }

                        if let pending = store.pendingApproval {
                            ApprovalCard(
                                pending: pending,
                                isBusy: store.isActiveChatBusy,
                                approve: store.approvePending,
                                deny: store.denyPending
                            )
                            .id("pending-approval")
                        }

                        if store.activeChatFlow.phase == .executing {
                            ChatProgressCard(
                                title: "Executing approved task",
                                detail: "The bound execution is running through CAPT RuntimeService. Model output remains evidence until separately verified."
                            )
                            .id("chat-executing")
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
                enabled: store.canComposeInActiveChat
            ) {
                guard store.canComposeInActiveChat else { return }
                let text = draft
                store.submitPrompt(text)
                draft = ""
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

private struct ChatProgressCard: View {
    let title: String
    let detail: String

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            ProgressView()
                .controlSize(.small)
            VStack(alignment: .leading, spacing: 4) {
                Text(title).font(.headline)
                Text(detail).font(.callout).foregroundStyle(.secondary)
            }
            Spacer()
        }
        .padding(14)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 14))
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
            if let expiresAt = pending.expiresAt {
                LabeledContent(
                    "Expires",
                    value: expiresAt.formatted(date: .omitted, time: .standard)
                )
                .font(.caption)
            }
            HStack {
                Button("Deny", role: .destructive, action: deny)
                    .disabled(isBusy || pending.isExpired())
                Spacer()
                Button("Approve & Run", action: approve)
                    .buttonStyle(.borderedProminent)
                    .disabled(isBusy || pending.isExpired())
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
