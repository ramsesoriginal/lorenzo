# 0291 - Inventory mobile: a native Android inventory companion

Status: accepted

## Context

Players need quick access to their characters' inventories at the table, including previously downloaded information when connectivity drops. The first mobile app is a narrow inventory reader with note creation, built on the existing REST API. This records the decisions implemented in `apps/inventory-mobile`; no RFC is needed for this agreed slice.

## Decision

- Ship **Lorenzo Inventory** as `apps/inventory-mobile`, application ID `io.lorenzo.inventory`, for Android 9+ (API 28). Use Kotlin, Jetpack Compose and Material 3, JDK 17, the committed Gradle wrapper, and the Android SDK versions declared by the app. Use the shared Lorenzo mark, palette, Geist, Newsreader and attributed icons.
- Keep two Gradle modules in this app: `core` holds the Android-independent typed REST adapter (OkHttp and kotlinx.serialization); `app` owns Compose, lifecycle-aware state, Room and WorkManager. Construction uses a small explicit dependency container. Extract a package only when another app needs it.
- Connect through account hub using the existing device-code flow and personal access tokens ([ADR 0268](0268-personal-access-tokens-api.md), [ADR 0269](0269-personal-access-tokens-hub-and-cli.md)). Existing token secrets may also be pasted. Tokens act as the user; there is no new native Authgear client or redirect URI. Sign-out clears credentials, cached data and pending notes; server-side revocation remains in account hub.
- Read the user's characters across libraries from `/me`, including co-piloted characters, and their inventories through the held-by route. Preserve equipped, carried-container and elsewhere grouping, quantities, visible descriptions, stats and tags. Inventory operations are read-only; notes are the sole write and default to the private audience.
- Encrypt credentials, snapshots and queued note payloads with Android Keystore-backed AES-GCM and fresh nonces. Disable backup and device transfer. Scope the cache by credential, check sessions before persisting responses and clear local access on 401. Remove stale snapshots on roster changes and 403/404. Offline reads can retain previously downloaded information until the device learns of revocation.
- Persist a note draft before networking. WorkManager retries transient failures with connectivity constraints and exponential backoff. A stable client UUID makes creation replay-safe; granting the character access is an idempotent PUT. Keep the draft pending until both writes and readback succeed; retain permanent failures for explicit retry.
- Render Markdown natively with Markwon. Unsupported LorenzoScript extensions remain visible as source. Full native LorenzoScript support is a later compatibility slice; do not embed a WebView or the TypeScript engine for this app.
- Register the app in root mise, CI's declared dependency graph, release-please, grouped Gradle Dependabot updates, Kotlin formatting hooks and the `app:inventory-mobile` scope label. The consumed-contract checker runs when the app or API changes; the brand dependency triggers app checks when copied brand assets change. CI installs the declared Android platform and Build Tools before lint, unit tests and APK/bundle builds.
- Release-please's `version.txt` is the single source of the stable `major.minor.patch` version. Derive Android's `versionCode` as `major * 1_000_000 + minor * 1_000 + patch + 1`, with minor and patch below 1,000 and the result within Google Play's 2,100,000,000 limit. Every distributed release needs a new version; rebuilt artifacts of the same version share a code. See [Android's versioning guidance](https://developer.android.com/studio/publish/versioning).
- Distribution for this slice is a locally built debug APK installed on a connected phone or emulator. Build an unsigned release bundle for validation. Play Store publishing, signing credentials and a deployment workflow wait for an explicitly scoped distribution decision.

## Not in scope

Inventory mutations, a GM catalog editor, iOS, full LorenzoScript compatibility, analytics and app-store publishing.

## Consequences

Native UI and durable local data support use at the table without connectivity. The Kotlin adapter is a second implementation of the REST contracts, so contract checks and HTTP tests are required alongside repository tests. Offline information cannot be remotely erased while the phone is disconnected. Notes remain visible as pending until their complete synchronization succeeds. Android SDK setup is now part of both contributor setup and CI, and semantic version bumps advance the installable app's version code automatically.
