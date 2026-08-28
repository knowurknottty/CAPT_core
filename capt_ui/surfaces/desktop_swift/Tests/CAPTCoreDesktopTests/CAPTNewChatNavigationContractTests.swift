import XCTest

final class CAPTNewChatNavigationContractTests: XCTestCase {
    func testGlobalNewChatCommandRoutesToChatSurface() throws {
        let here = URL(fileURLWithPath: #filePath)
        let packageRoot = here
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        let appURL = packageRoot.appendingPathComponent("Sources/CAPTNativeMac/App/CAPTNativeMacApp.swift")
        let contentURL = packageRoot.appendingPathComponent("Sources/CAPTNativeMac/Views/ContentView.swift")
        let app = try String(contentsOf: appURL, encoding: .utf8)
        let content = try String(contentsOf: contentURL, encoding: .utf8)

        XCTAssertTrue(content.contains("@Binding var selection: CAPTSidebarSection"))
        XCTAssertTrue(app.contains("ContentView(store: store, selection: $selection)"))
        XCTAssertTrue(app.contains("store.newChat()\n                    selection = .chat"))
    }
}
