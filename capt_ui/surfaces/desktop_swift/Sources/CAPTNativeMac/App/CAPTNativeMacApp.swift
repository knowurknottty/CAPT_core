import SwiftUI
import AppKit

final class CAPTAppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
    }
}

@main
struct CAPTNativeMacApp: App {
    @NSApplicationDelegateAdaptor(CAPTAppDelegate.self) private var appDelegate
    @StateObject private var store = CAPTOperatorStore()

    var body: some Scene {
        WindowGroup("CAPT", id: "capt-main") {
            ContentView(store: store)
                .frame(minWidth: 1120, minHeight: 720)
                .task { store.connect() }
        }
        .defaultSize(width: 1280, height: 820)
        .commands {
            CommandGroup(after: .appInfo) {
                Button("Reconnect CAPT Runtime") { store.connect() }
                    .keyboardShortcut("r", modifiers: [.command, .shift])
            }
        }
    }
}
