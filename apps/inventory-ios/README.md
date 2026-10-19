# Lorenzo Inventory for iOS

Native SwiftUI companion for iPhone and iPad, iOS 17+. [RFC 0045](../../docs/rfcs/0045-inventory-on-ios.md), [ADR 0307](../../docs/adr/0307-inventory-ios-and-altstore-testing.md).

## At the table

Connect through account hub's device code or a personal access token. Read your characters' inventories across libraries, including co-piloted characters: Equipped, containers, things held elsewhere, quantities, stats, tags and source-labelled preferred-language descriptions. Search names/tags. Inventory operations are read-only.

Notes hold ordered LorenzoScript text and pictures. Ordinary Markdown renders natively; unsupported syntax remains source. Choose a picture or take a photo, add text, move/remove parts and expand Who can read this for public, character or group readers. Notes default to the selected character; library administrators and campaign GMs retain existing access. One audience covers the whole note.

Keep draft saves encrypted edits/media locally; Save note queues a durable upload. Pending/failed notes retain Retry. Stable IDs make retries safe; full content, order, pictures and audience must be confirmed before sent. Downloaded information works offline until the device learns a revocation. Sign-out clears credentials, drafts and caches. iOS controls background execution: retry happens on opening the app, restored connectivity and granted background time.

## Free AltStore Classic installation on Windows

1. Download the Lorenzo-Inventory-iOS CI artifact and extract its ZIP to find Lorenzo-Inventory.ipa.
2. Install AltServer and AltStore Classic following the [official Windows guide](https://faq.altstore.io/altstore-classic/how-to-install-altstore-windows), including current iTunes/iCloud requirements. Connect the iPhone by USB for setup.
3. Sign in locally in AltServer with a free Apple account, trust the computer and enable Developer Mode when requested. Apple credentials never belong in this repository, CI secrets or chat.
4. Transfer the IPA to Files on the iPhone. In AltStore Classic, open My Apps, tap + and select it. AltStore signs the app locally.
5. Open Lorenzo Inventory and connect through account hub.

Use Classic, not PAL. Free accounts allow three active sideloaded apps including AltStore, and need refreshing every seven days. Keep AltServer available and refresh before expiration; [AltStore's guide](https://faq.altstore.io/altstore-classic/your-altstore). No paid membership or jailbreak. TestFlight/App Store publishing is outside this slice.

The IPA contains an unsigned arm64 device app, not a simulator build; local signing is required. Actual AltStore installation, camera permissions and photo acquisition need a physical-device check.

## Build and test

On macOS with Xcode 16.4 (pinned in CI) and an installed iOS simulator runtime:

    mise run lint
    mise run test
    mise run build

Simulator tests use local ad-hoc signing for private Keychain access, with no Apple account or certificate. The device IPA remains unsigned for AltStore.

Public macOS CI runs native contract, encryption, session, image-orientation and replay tests plus a simulator flow against a localhost fixture. Builds produce build/Lorenzo-Inventory.ipa without certificates; simulator results are retained as CI artifacts. Swift CodeQL traces a fresh native build.

The dependency-free Python generator creates an ignored Xcode project from Sources/Resources/UITests. Windows/Linux can run Python project/contract checks; native tests need Xcode. The app owns dev/lint/test/build, API/brand dependency declarations, a consumed-contract snapshot, independent version.txt/release-please entry and Swift dependency discovery.

CryptoKit AES-GCM uses fresh nonces and a random device-only Keychain key; the token also stays in Keychain. Ciphertext has file protection and backup exclusion. No paid entitlement or access group. Session generations fence responses, including same-token reconnections; cache epochs fence revocations. No telemetry, remote fonts, WebView, credential logging or redirects with bearer tokens. Pictures use authenticated payload-ID routes. Copied media becomes bounded orientation-correct JPEGs without changing originals. Font licenses are bundled in Resources.
