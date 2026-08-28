import SwiftUI
import AppKit
import OSLog
import CAPTCoreDesktop

enum CAPTAppTelemetry {
    static let log = Logger(subsystem: "com.inversionlabs.capt.lab", category: "lifecycle")
}

final class CAPTAppDelegate: NSObject, NSApplicationDelegate {
    func applicationWillFinishLaunching(_ notification: Notification) {
        CAPTAppTelemetry.log.notice("applicationWillFinishLaunching")
        NSApp.setActivationPolicy(.regular)
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        CAPTAppTelemetry.log.notice("applicationDidFinishLaunching windows=\(NSApp.windows.count)")
        NSApp.activate(ignoringOtherApps: true)
        DispatchQueue.main.asyncAfter(deadline: .now() + 1) {
            CAPTAppTelemetry.log.notice("postLaunch windows=\(NSApp.windows.count)")
        }
    }
}

@main
struct CAPTNativeMacApp: App {
    @NSApplicationDelegateAdaptor(CAPTAppDelegate.self) private var appDelegate
    @StateObject private var store: CAPTOperatorStore
    @State private var selection: CAPTSidebarSection = .chat

    init() {
        let environment = ProcessInfo.processInfo.environment
        let stateRoot: URL
        if let override = environment["CAPT_LAB_STATE_DIR"], !override.isEmpty {
            stateRoot = URL(fileURLWithPath: NSString(string: override).expandingTildeInPath, isDirectory: true)
        } else {
            stateRoot = FileManager.default.homeDirectoryForCurrentUser
                .appendingPathComponent(".capt-inversion-labs", isDirectory: true)
        }
        let sessionStore = CAPTEncryptedSessionStore(
            fileURL: stateRoot.appendingPathComponent("ui/native_sessions.enc"),
            keyProvider: CAPTKeychainSessionKeyProvider(
                service: "com.inversionlabs.capt.lab.native-session-cache",
                account: "signed-session-key-v1"
            )
        )
        _store = StateObject(wrappedValue: CAPTOperatorStore(
            runtime: CAPTBackgroundRuntime(stateDirectory: stateRoot.path),
            reconciliationRuntime: CAPTBackgroundRuntime(stateDirectory: stateRoot.path),
            sessionStore: sessionStore
        ))
    }

    var body: some Scene {
        Window("Inversion Labs CAPT", id: "capt-lab-main") {
            ContentView(store: store, selection: $selection)
                .frame(minWidth: 1120, minHeight: 720)
                .onAppear { CAPTAppTelemetry.log.notice("ContentView appeared windows=\(NSApp.windows.count)") }
                .task { store.connect() }
        }
        .defaultSize(width: 1280, height: 820)
        .commands {
            CommandGroup(replacing: .newItem) {
                Button("New Chat") {
                    store.newChat()
                    selection = .chat
                }
                .keyboardShortcut("n", modifiers: [.command])
            }
            CommandGroup(after: .appInfo) {
                Button("Reconnect CAPT Runtime") { store.connect() }
                    .keyboardShortcut("r", modifiers: [.command, .shift])
            }
        }
    }
}
