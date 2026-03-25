// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "GearboxUI",
    platforms: [
        .macOS(.v13)
    ],
    targets: [
        .executableTarget(
            name: "GearboxUI",
            dependencies: [],
            path: "Sources/GearboxUI",
            resources: [.process("Resources")]
        ),
        .testTarget(
            name: "GearboxUITests",
            dependencies: ["GearboxUI"],
            path: "Tests/GearboxUITests"
        )
    ]
)
