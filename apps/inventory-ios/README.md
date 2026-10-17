# Lorenzo Inventory for iOS

Native SwiftUI companion for iOS 17+. Decisions: [RFC 0045](../../docs/rfcs/0045-inventory-on-ios.md), [ADR 0307](../../docs/adr/0307-inventory-ios-and-altstore-testing.md).

The app uses the existing Lorenzo API; inventories are read-only and notes are the sole write. The implementation is built in tested slices on this feature branch. macOS CI supplies Xcode; Apple credentials and paid distribution are outside this slice.

Run mise run lint, test or build from this directory on macOS with Xcode. The build task creates build/Lorenzo-Inventory.ipa, an unsigned device app for local AltStore Classic signing. Windows/Linux can run the Python contract/config checks; native compilation and simulator tests require macOS CI.
