// swift-tools-version: 5.9
import PackageDescription
let package = Package(name: "InventoryCore", platforms: [.macOS(.v13), .iOS(.v17)],
    products: [.library(name: "InventoryCore", targets: ["InventoryCore"])],
    targets: [.target(name: "InventoryCore", path: "Sources/Core"),
              .testTarget(name: "InventoryCoreTests", dependencies: ["InventoryCore"], path: "Tests")])
