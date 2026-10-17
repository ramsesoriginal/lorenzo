// swift-tools-version: 5.9
import PackageDescription
let package = Package(name: "InventoryCore", platforms: [.macOS(.v13), .iOS(.v17)],
    products: [.library(name: "InventoryCore", targets: ["InventoryCore"])],
    targets: [.target(name: "InventoryCore", path: "Sources/Core"),
              .target(name: "InventoryState", dependencies: ["InventoryCore"], path: "Sources/App",
                      exclude: ["Views.swift", "LorenzoInventoryApp.swift"], sources: ["InventoryStore.swift"]),
              .testTarget(name: "InventoryCoreTests", dependencies: ["InventoryCore"], path: "Tests"),
              .testTarget(name: "InventoryStateTests", dependencies: ["InventoryCore", "InventoryState"], path: "StateTests")])
