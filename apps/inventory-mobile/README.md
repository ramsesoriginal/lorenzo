# inventory-mobile

Lorenzo's native Android companion for character inventories. Kotlin, Jetpack Compose and Material 3; Android 9+ (API 28). The app launches as **Lorenzo Inventory** and uses application ID `io.lorenzo.inventory`.

The app decision is [ADR 0291](../../docs/adr/0291-inventory-mobile-native-android-app.md).

## Install or run

Open this directory as a project in Android Studio. Use JDK 17 and install Android SDK 37.0 and Build Tools 36.0.0 in SDK Manager. The Gradle wrapper is included; no global Gradle installation is needed.

```sh
./gradlew :app:assembleDebug
./gradlew :app:installDebug   # connected phone/emulator, USB debugging enabled
```

For command-line builds, set `ANDROID_HOME` to the SDK directory (or set `sdk.dir` in an untracked `local.properties`). Accept its licenses with `sdkmanager --licenses` and install `sdkmanager "platform-tools" "platforms;android-37.0" "build-tools;36.0.0"`. CI installs the same packages explicitly.

The app participates in root `mise run lint`, `test` and `check`; install JDK 17 with `mise install` from this directory and set up the SDK before running them. `mise run //apps/inventory-mobile:dev` installs the debug app on a connected device.

On Windows use `gradlew.bat`. Debug APK: `app/build/outputs/apk/debug/app-debug.apk`.

## Sign in

Tap **Connect with account hub**, then **Open account hub**. Sign in with Lorenzo's existing Authgear login if needed and approve the code. Return to the app; it obtains a personal access token and finishes connecting automatically. Codes expire after ten minutes. The device flow uses `/device-codes` and `/device-codes/token`, including the API's polling interval and slow-down response. This needs no native Authgear client registration or redirect URI.

Alternatively paste an existing `lor_pat_…` token. The profile lists token metadata and revocation; it does not reveal an already-issued secret. Connect a device if you do not have that secret.

Tokens are full-as-you, as defined by Lorenzo ADR 0268. Sign out clears the phone's credential, cache and pending notes. Revoke the device's token in account hub when you want to invalidate it on the server.

## At the table

- All characters in `/me.players[].characters`, including co-piloted characters, across libraries. Deduplicated by library and entity ID; GM status and tenant-wide membership are not required.
- Inventory comes from `GET /tenants/{tenant_id}/item-instances/held-by/{entity_id}`. Equipped items, nested carried containers and items held elsewhere retain the API's grouping and quantities. Search matches names and tags locally.
- Item details open immediately from that inventory snapshot: descriptions from every visible source in the preferred language, physical/economic/combat stats, tags and ownership. Notes are fetched separately with full pagination. All inventory operations are read-only.
- Notes are the sole write. One information note can hold ordered LorenzoScript text and pictures. Add text, choose a picture from the system gallery picker, or take a photo; move/remove parts within the existing note editor.
- **Who can read this** starts with the selected character explicitly checked. Choose other characters or groups, or make the information public. GMs and library administrators retain role access; groups follow current membership. Text and images share this audience. Offline choices retain their IDs and use downloaded recipient names; rejected selections never become public automatically.
- Composers, selected/captured pictures and submitted notes persist encrypted before network work starts. Closing an editor retains its draft; Discard removes it. Capture requests stay bound to their original note across navigation and recreation. A canceled or late result cannot attach to a newer request.
- WorkManager retries transient failures with network constraints and exponential backoff. Stable information/payload IDs recover lost responses; text, payload ordering and explicit audiences are checked before completion. Until the complete bundle and audience are read back, the note remains visibly pending. Conflicts/permanent rejections retain the draft with Retry.
- Attached pictures render natively through authenticated API reads, with encrypted offline copies. Tap to enlarge and zoom. Gallery/camera images are decoded with orientation, bounded to 4,096 pixels on the long edge and roughly eight megapixels, and re-encoded as JPEG up to 2 MiB without changing the original. Camera output is a temporary private file, removed after staging/cancellation or sign-out; no camera/storage permission or OCR is added.
- Cached screens remain available offline and refresh on navigation or pull-to-refresh. The roster prefetches the first three character inventories, which include descriptions and stats. Download time is displayed. Notes cache when the item is opened.
- Dark/light follows the system. Material components provide touch targets, semantics, insets and font scaling; Lorenzo's actual master mark, Geist, Newsreader and palette provide the identity. Gold is reserved for the mark.

## Structure and choices

`core` is an Android-independent Kotlin module with typed REST contracts, cancellable OkHttp requests and kotlinx.serialization. It can be reused by another Kotlin client. `app/data` owns Room, encrypted snapshots and the durable note queue. The repository is the source of truth. `InventoryViewModel` owns immutable UI state and coroutines; Compose collects it with lifecycle awareness. A small application-scoped dependency container keeps construction explicit without a DI framework.

This is one narrow deployable app, not a speculative multi-feature architecture. AGP uses built-in Kotlin; Compose uses the Kotlin compiler plugin and a BOM. Versions live in `gradle/libs.versions.toml`. Compile/target SDK 37 is a stable baseline; upgrades should include a build and device validation, not only dependency bumps.

The native adapter mirrors the same endpoints as `packages/api-client` without importing TypeScript into Android. `contracts/consumed.json` records consumed wire shapes from deployed API 0.7.0, checked against main `126e959` (2026-10-14). Compatible extra response fields are ignored, including future payload types. The contract checker rejects removed fields, incompatible types, missing routes and new required write fields.

Markdown descriptions and notes render natively through Markwon. Unsupported LorenzoScript extensions (live stat formulas, entity preview links, editor blocks, inline remote images) remain visible as source rather than guessed results. The TypeScript LorenzoScript engine is not embedded: a full native implementation is a separate compatibility slice. Bundle text preserves what was entered. Attached picture payloads use the native protected-image viewer.

No WebView, telemetry, advertising, analytics, HTTP logging or remote font fetches. Authenticated requests never follow redirects. Room snapshot/draft payloads, chunked media and credentials use AES-GCM with fresh nonces and an Android Keystore key. Backup/device transfer is disabled. Cache keys are credential-scoped; session-checked persistence prevent a prior session response from repopulating a signed-out cache. A detected 401 clears local access; roster changes and 403/404 remove stale snapshots. Previously downloaded information remains readable while offline until the device learns about a revocation.

## Versioning and distribution

Release-please updates `version.txt` and the changelog independently for this app. The stable `major.minor.patch` version supplies `versionName`; `versionCode` is `major * 1_000_000 + minor * 1_000 + patch + 1`. Minor and patch must each be below 1,000, and the resulting code must fit Google Play's limit. A distributed release needs a version bump; rebuilding that version keeps its code.

Current distribution is local installation of the debug APK. `mise run //apps/inventory-mobile:build` also produces an unsigned release bundle at `app/build/outputs/bundle/release/app-release.aab` for validation. Store publishing and release signing are deferred; no deployment workflow is needed for this slice.

## Checks

```sh
./gradlew :core:test :app:testDebugUnitTest :app:lintDebug :app:assembleDebug
./gradlew :app:connectedDebugAndroidTest # emulator: orientation, Room migration, native composer
python3 scripts/check_contract.py ../api/openapi.json
# In Lorenzo, generate the current schema and check it:
mise run //apps/inventory-mobile:check-schema
```

Repository tests cover non-blocking local note persistence, logout during a request, replay after a failed reader write, and retaining permanently rejected drafts. HTTP tests exercise real requests against MockWebServer: roster deduplication, locale selection, unknown fields, zero values, actual inventory route, note pagination, stable note IDs/private defaults/reader calls, error parsing and redirect credential protection. No account token is needed. A real-account smoke test remains necessary to verify your character roster and notes against production; automated tests never write to production.

The Room 1→2 migration preserves existing snapshots and queued notes, and adds encrypted composer
metadata and media chunks. Each encrypted chunk holds at most 64 KiB of plaintext, keeping large
pictures out of a single Room cursor row. Existing plain-text queued notes remain readable and
sync through their original contract.

Native recovery tests cover lost upload/order/audience responses, conflicting readers or order,
original capture targeting after recreation, cancellation, logout, and learned image revocation
including an older download arriving afterward. Emulator tests verify EXIF rotation, unchanged
original bytes, the actual FileProvider, the Room upgrade, and the mixed note UI. They use local
fixtures and never sign into a real account or invoke a physical camera.
