// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "CAPTCoreDesktop",
    platforms: [.macOS(.v13)],
    products: [
        .library(name: "CAPTCoreDesktop", targets: ["CAPTCoreDesktop"]),
        .executable(name: "CAPTNativeMac", targets: ["CAPTNativeMac"]),
    ],
    targets: [
        .target(name: "CAPTCoreDesktop"),
        .executableTarget(
            name: "CAPTNativeMac",
            dependencies: ["CAPTCoreDesktop"]
        ),
        .testTarget(
            name: "CAPTCoreDesktopTests",
            dependencies: ["CAPTCoreDesktop"]
        ),
    ]
)
