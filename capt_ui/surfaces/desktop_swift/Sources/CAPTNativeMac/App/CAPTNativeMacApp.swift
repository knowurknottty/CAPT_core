import SwiftUI
import AppKit
import OSLog

enum CAPTAppTelemetry {
    static let log = Logger(subsystem: "com.inversionlabs.capt", category: "lifecycle")
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
    @StateObject private var store = CAPTOperatorStore()

    var body: some Scene {
        Window("CAPT Chat", id: "capt-main") {
            ContentView(store: store)
                .frame(minWidth: 1120, minHeight: 720)
                .onAppear { CAPTAppTelemetry.log.notice("ContentView appeared windows=\(NSApp.windows.count)") }
                .task { store.connect() }
        }
        .defaultSize(width: 1280, height: 820)
        .commands {
            CommandGroup(replacing: .newItem) {
                Button("New Chat") { store.newChat() }
                    .keyboardShortcut("n", modifiers: [.command])
            }
            CommandGroup(after: .appInfo) {
                Button("Reconnect CAPT Runtime") { store.connect() }
                    .keyboardShortcut("r", modifiers: [.command, .shift])
            }
        }
    }
}
