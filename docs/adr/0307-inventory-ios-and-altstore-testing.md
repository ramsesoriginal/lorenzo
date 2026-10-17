# 0307 - Inventory on iOS and AltStore testing

Status: accepted, decided with the maintainer on 2026-10-17. Implements [RFC 0045](../rfcs/0045-inventory-on-ios.md).

## Context

ADR 0291 deliberately scoped the first native companion to Android. The maintainer now wants the same inventory and note experience on iPhone, owns no Mac, and has chosen free AltStore Classic testing rather than TestFlight.

## Decision

- Add apps/inventory-ios, Lorenzo Inventory, using Swift and SwiftUI for iOS 17+. Keep Android intact. A small Foundation core, Swift Package tests and native views use the existing REST API without a new backend or cross-platform framework.
- Use account-hub device authorization and PAT sign-in (ADR 0268/0269). Tokens are full-as-user. Never follow redirects with credentials, load arbitrary payload URLs, log credentials or embed Apple credentials.
- Match Android's read-only inventory scope, source-labelled preferred-language descriptions, stats/tags and ordered notes. Text is LorenzoScript; render ordinary Markdown and retain unsupported syntax as source. Notes are the sole write. Preserve separate Information audiences, stable information/payload IDs, optimistic preconditions and complete content/order/audience readback (ADR 0304/0306).
- Encrypt private snapshots, drafts and pictures with CryptoKit AES-GCM; keep the random encryption key and token in device-only Keychain items. Store ciphertext under Application Support with backup excluded and file protection. Scope stored content to the credential. Every request and persistence operation checks a session generation, even when reconnecting with the same token. Sign-out/401 clear credentials, snapshots, drafts and staged media; learned 403/404/roster revocation fences stale reads and cached pictures.
- Save drafts and selected/captured media before upload. Use PhotosPicker and a native camera picker, bounded orientation-aware JPEG normalization and untouched originals. Persist edits, explicit recipient IDs, payload order and retry progress. Failed validation never widens an audience. Retry on foreground, restored connectivity and permitted background time, with bounded exponential backoff and manual Retry for permanent failures. iOS background execution is best-effort, not a promise of immediate delivery while closed.
- Use iOS semantic controls, Dynamic Type, system appearance and Lorenzo's own fonts, mark and palette. Keep ordinary note creation simple; additional parts and audience selection stay within the composer.
- Build, unit-test and simulator-test on standard GitHub macOS runners for this public repository. The normal node's lint/test/build tasks remain explicit about requiring Xcode. Declare its API/brand dependencies, schema checks, independent release version and CI coverage. A deterministic Python generator writes the Xcode project from local source paths; no downloaded generator or third-party runtime package is needed.
- Build an unsigned arm64 device app and package Payload/LorenzoInventory.app in an IPA. It is not directly installable until AltStore Classic signs it locally. Document Windows setup, Developer Mode, importing the IPA, free-account three-app/seven-day limits and refresh. No certificate, provisioning profile or Apple account in the repository or CI. Simulator evidence does not replace the user's physical gallery/camera/install check.
- Start at version 0.1.0 with an independent release-please simple version. No automatic deployment, TestFlight, App Store enrollment, paid service, inventory mutations, full LorenzoScript engine or broader authoring surface.

## Consequences

An iPhone companion adds a second native API adapter, so compatible wire-shape, multipart and HTTP tests are required. Native UI and encrypted storage remain platform-specific. Free CI covers builds and simulator behavior without a personal Mac; actual AltStore installation and camera behavior require the user's iPhone. Offline access cannot learn remote revocations until reconnecting. Locally signing with AltStore changes the signing identity: avoid access groups, push capabilities and other paid entitlements.

## References

- [GitHub standard runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
- [AltStore Classic on Windows](https://faq.altstore.io/altstore-classic/how-to-install-altstore-windows)
- [Apple background strategies](https://developer.apple.com/documentation/backgroundtasks/choosing-background-strategies-for-your-app)
