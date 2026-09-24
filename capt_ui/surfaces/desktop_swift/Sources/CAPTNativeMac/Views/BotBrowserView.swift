import SwiftUI
import CAPTCoreDesktop

struct BotBrowserView: View {
    @ObservedObject var store: CAPTOperatorStore
    @State private var selectedID: String?

    var body: some View {
        HSplitView {
            botList
                .frame(minWidth: 270, idealWidth: 300, maxWidth: 340)
            botDetail
                .frame(minWidth: 470)
        }
        .navigationTitle("Bots")
        .onAppear { store.refreshBots() }
    }

    private var botList: some View {
        VStack(spacing: 0) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("CAPT BOT FOUNDATION")
                        .font(.caption2.weight(.semibold))
                        .tracking(1.2)
                        .foregroundStyle(InversionTone.cyan.color)
                    Text("Durable identities and cognition policy")
                        .font(.callout.weight(.semibold))
                }
                Spacer()
                InversionStatusBadge("\(store.bots.count) registered", tone: .cyan, monospaced: true)
            }
            .padding(14)
            .background(.ultraThinMaterial)

            InversionDivider()
            if store.bots.isEmpty {
                VStack(spacing: 10) {
                    Image(systemName: "person.2")
                        .font(.system(size: 28))
                        .foregroundStyle(.secondary)
                    Text("No registered Bots")
                        .font(.headline)
                    Text("The runtime exposes CAPT Bot Foundation, but this ledger has no Bot identities yet.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                }
                .padding(24)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                List(store.bots, selection: $selectedID) { bot in
                    VStack(alignment: .leading, spacing: 5) {
                        HStack {
                            Text(bot.displayName)
                                .font(.callout.weight(.semibold))
                            Spacer()
                            InversionStatusBadge(bot.roleKind.uppercased(), tone: .cyan)
                        }
                        Text(bot.role.isEmpty ? bot.id : bot.role)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Text(bot.id)
                            .font(.caption2.monospaced())
                            .foregroundStyle(.tertiary)
                    }
                    .tag(bot.id)
                    .padding(.vertical, 4)
                }
                .listStyle(.inset)
            }
        }
    }

    @ViewBuilder
    private var botDetail: some View {
        if let bot = selectedBot {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    InversionPanel(tone: .cyan, padding: 20) {
                        VStack(alignment: .leading, spacing: 14) {
                            HStack(alignment: .top) {
                                InversionSectionHeader(
                                    bot.displayName,
                                    eyebrow: "BOT IDENTITY",
                                    detail: bot.id,
                                    symbol: "person.2",
                                    tone: .cyan
                                )
                                Spacer()
                                InversionStatusBadge(bot.roleKind.uppercased(), tone: .cyan)
                            }
                            InversionDivider()
                            InversionKeyValueRow("role", value: bot.role.isEmpty ? "unspecified" : bot.role)
                            InversionKeyValueRow("mission", value: bot.missionID ?? "unbound", monospaced: true)
                            InversionKeyValueRow("primary model", value: bot.primaryModel ?? "runtime-selected")
                            InversionKeyValueRow(
                                "fallbacks",
                                value: bot.fallbackModels.isEmpty
                                    ? "none"
                                    : bot.fallbackModels.joined(separator: " · ")
                            )
                        }
                    }

                    InversionPanel(tone: .violet) {
                        VStack(alignment: .leading, spacing: 10) {
                            InversionSectionHeader(
                                "Cognition & locality",
                                detail: "Persistent policy composition; not execution authority.",
                                symbol: "brain.head.profile",
                                tone: .violet
                            )
                            InversionDivider()
                            InversionKeyValueRow("promotion mode", value: bot.promotionMode)
                            InversionKeyValueRow("default runtime", value: bot.defaultRuntime)
                            InversionKeyValueRow("private data", value: bot.privateData)
                            InversionKeyValueRow(
                                "delegation",
                                value: bot.mayDelegate
                                    ? "allowed · depth \(bot.maxSpawnDepth)"
                                    : "off"
                            )
                        }
                    }

                    InversionPanel(tone: .amber) {
                        VStack(alignment: .leading, spacing: 10) {
                            InversionSectionHeader(
                                "Authority boundary",
                                detail: "Bot identity is durable policy state. Credentials, capability grants, and live leases are intentionally absent from this projection.",
                                symbol: "lock.shield",
                                tone: .amber
                            )
                            InversionDivider()
                            InversionKeyValueRow(
                                "authority template",
                                value: bot.authorityTemplateRef ?? "none",
                                monospaced: true
                            )
                            if let createdAt = bot.createdAt {
                                InversionKeyValueRow("created", value: createdAt, monospaced: true)
                            }
                        }
                    }
                }
                .padding(InversionVisualLanguage.pagePadding)
                .frame(maxWidth: 920)
                .frame(maxWidth: .infinity, alignment: .topLeading)
            }
        } else {
            VStack(spacing: 10) {
                Image(systemName: "person.2")
                    .font(.system(size: 32))
                    .foregroundStyle(.secondary)
                Text("Select a Bot")
                    .font(.headline)
                Text("Inspect identity, role, model strategy, cognition policy, locality, and delegation limits.")
                    .font(.callout)
                    .foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }

    private var selectedBot: CAPTBotSummary? {
        if let selectedID, let exact = store.bots.first(where: { $0.id == selectedID }) {
            return exact
        }
        return store.bots.first
    }
}
