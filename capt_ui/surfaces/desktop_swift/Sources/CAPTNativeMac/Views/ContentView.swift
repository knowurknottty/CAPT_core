import SwiftUI

struct ContentView: View {
    @ObservedObject var store: CAPTOperatorStore

    var body: some View {
        NavigationSplitView {
            SidebarView(selection: $store.selectedSection, store: store)
                .navigationSplitViewColumnWidth(min: 170, ideal: 210, max: 260)
        } detail: {
            VStack(spacing: 0) {
                HSplitView {
                    primaryView
                        .frame(minWidth: 560)
                    InspectorView(store: store)
                        .frame(minWidth: 280, idealWidth: 310, maxWidth: 380)
                }
                Divider()
                StatusBarView(store: store)
            }
        }
        .toolbar {
            ToolbarItemGroup {
                Button { store.refreshAll() } label: {
                    Label("Refresh", systemImage: "arrow.clockwise")
                }
                Button { store.connect() } label: {
                    Label("Connect", systemImage: "bolt.horizontal.circle")
                }
            }
        }
    }

    @ViewBuilder
    private var primaryView: some View {
        switch store.selectedSection {
        case .chat:
            ChatView(store: store)
        case .missions:
            MissionBrowserView(store: store)
        case .approvals:
            ApprovalQueueView(store: store)
        case .providers:
            ProviderControlView(store: store)
        case .memory:
            MemoryContextView(store: store)
        case .evidence:
            EvidenceBrowserView(store: store)
        case .ledger:
            LedgerView(store: store)
        case .runtime:
            RuntimeControlView(store: store)
        case .settings:
            InfoSurface(
                title: "Settings",
                symbol: "gearshape",
                detail: "CAPT state paths follow CAPT_STATE_DIR or ~/.capt. Credentials remain outside the app."
            )
        }
    }
}

private struct InfoSurface: View {
    let title: String
    let symbol: String
    let detail: String

    var body: some View {
        VStack(spacing: 14) {
            Image(systemName: symbol)
                .font(.system(size: 34))
                .foregroundStyle(.secondary)
            Text(title).font(.title2.bold())
            Text(detail)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 440)
        }
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
