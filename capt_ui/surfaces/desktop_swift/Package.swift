// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "CAPTCoreDesktop",
    platforms: [.macOS(.v13)],
    products: [
        .library(name: "CAPTCoreDesktop", targets: ["CAPTCoreDesktop"]),
    ],
    targets: [
        .target(name: "CAPTCoreDesktop"),
    ]
)
