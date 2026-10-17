# 0045 - Lorenzo Inventory on iOS

Status: accepted, decided with the maintainer on 2026-10-17; decision in [ADR 0307](../adr/0307-inventory-ios-and-altstore-testing.md).

## Intent

Bring the Android inventory companion's current scope to iPhone without requiring the maintainer to own a Mac or buy a developer membership. Keep the existing API and Lorenzo's quiet, native interface.

## Agreed scope

SwiftUI, iOS 17+, a separate purpose-specific companion at apps/inventory-ios. Account-hub device authorization and personal access tokens; characters across libraries, inventory grouping and item details; private-by-default notes with ordered LorenzoScript text and pictures, explicit character/group audiences, gallery and camera acquisition. Encrypted offline snapshots, protected pictures and durable note drafts follow ADR 0291 and ADR 0306, including session fencing, stable replay identities and full readback before sent.

Build and test on standard public GitHub macOS runners. Produce an unsigned device IPA for the user's local AltStore Classic signing on Windows with a free Apple account. Apple credentials never enter CI. TestFlight, App Store, paid builders, inventory mutation and broader native LorenzoScript interpretation remain out of scope.

## Execution slices

1. Native sign-in, roster, inventories and item details with typed contracts and HTTP tests.
2. Encrypted offline storage, ordered note creation, audiences, protected pictures and acquisition; recovery and isolation tests.
3. Simulator flows, unsigned device artifact, Windows AltStore instructions and repository integration.

Each slice must be tested before proceeding; the complete accepted feature is the delivery target.
