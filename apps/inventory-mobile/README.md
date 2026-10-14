# inventory-mobile

Lorenzo's native Android companion for character inventories. Kotlin, Jetpack Compose and Material 3; Android 9+ (API 28). The app launches as **Lorenzo Inventory** and uses application ID `io.lorenzo.inventory`.

## Install or run

Open this directory as a project in Android Studio. Use JDK 17 and install Android SDK 37.0 and Build Tools 36.0.0 in SDK Manager. The Gradle wrapper is included; no global Gradle installation is needed.

```sh
./gradlew :app:assembleDebug
./gradlew :app:installDebug   # connected phone/emulator, USB debugging enabled
```

On Windows use `gradlew.bat`. Debug APK: `app/build/outputs/apk/debug/app-debug.apk`.

## Sign in

Tap **Connect with account hub**, then **Open account hub**. Sign in with Lorenzo's existing Authgear login if needed and approve the code. Return to the app; it obtains a personal access token and finishes connecting automatically. Codes expire after ten minutes. The device flow uses `/device-codes` and `/device-codes/token`, including the API's polling interval and slow-down response. This needs no native Authgear client registration or redirect URI.

Alternatively paste an existing `lor_pat_…` token. The profile lists token metadata and revocation; it does not reveal an already-issued secret. Connect a device if you do not have that secret.

Tokens are full-as-you, as defined by Lorenzo ADR 0268. Sign out clears the phone's credential, cache and pending notes. Revoke the device's token in account hub when you want to invalidate it on the server.

## At the table

- All characters in `/me.players[].characters`, including co-piloted characters, across libraries. Deduplicated by library and entity ID; GM status and tenant-wide membership are not required.
- Inventory comes from `GET /tenants/{tenant_id}/item-instances/held-by/{entity_id}`. Equipped items, nested carried containers and items held elsewhere retain the API's grouping and quantities. Search matches names and tags locally.
- Item details open immediately from that inventory snapshot: descriptions from every visible source in the preferred language, physical/economic/combat stats, tags and ownership. Notes are fetched separately with full pagination. All inventory operations are read-only.
- Notes are the sole write. They default to private: selected character players, campaign GMs and library administrators can read them. The public checkbox changes that audience explicitly.
- Submitted notes persist as encrypted drafts before network work starts. WorkManager retries transient failures with network constraints and exponential backoff. The stable UUID supplied to the API makes POST replay safe; adding the character reader is an idempotent PUT. Until both writes and a readback succeed, the note remains visibly pending. Permanent rejections retain the draft with Retry.
- Cached screens remain available offline and refresh on navigation or pull-to-refresh. The roster prefetches the first three character inventories, which include descriptions and stats. Download time is displayed. Notes cache when the item is opened.
- Dark/light follows the system. Material components provide touch targets, semantics, insets and font scaling; Lorenzo's actual master mark, Geist, Newsreader and palette provide the identity. Gold is reserved for the mark.

## Structure and choices

`core` is an Android-independent Kotlin module with typed REST contracts, cancellable OkHttp requests and kotlinx.serialization. It can be reused by another Kotlin client. `app/data` owns Room, encrypted snapshots and the durable note queue. The repository is the source of truth. `InventoryViewModel` owns immutable UI state and coroutines; Compose collects it with lifecycle awareness. A small application-scoped dependency container keeps construction explicit without a DI framework.

This is one narrow deployable app, not a speculative multi-feature architecture. AGP uses built-in Kotlin; Compose uses the Kotlin compiler plugin and a BOM. Versions live in `gradle/libs.versions.toml`. Compile/target SDK 37 is a stable baseline; upgrades should include a build and device validation, not only dependency bumps.

The native adapter mirrors the same endpoints as `packages/api-client` without importing TypeScript into Android. `contracts/consumed.json` records consumed wire shapes from deployed API 0.7.0, checked against main `126e959` (2026-10-14). Compatible extra response fields are ignored, including future payload types. The contract checker rejects removed fields, incompatible types, missing routes and new required write fields.

Markdown descriptions and notes render natively through Markwon. Unsupported LorenzoScript extensions (live stat formulas, entity preview links, editor blocks, protected images) remain visible as source rather than guessed results. The TypeScript LorenzoScript engine is not embedded: a full native implementation is a separate compatibility slice. Notes send the entered text with outer whitespace trimmed.

No WebView, telemetry, advertising, analytics, HTTP logging or remote font fetches. Authenticated requests never follow redirects. Room snapshot/draft payloads and credentials use AES-GCM with fresh nonces and an Android Keystore key. Backup/device transfer is disabled. Cache keys are credential-scoped; session-checked persistence prevent a prior session response from repopulating a signed-out cache. A detected 401 clears local access; roster changes and 403/404 remove stale snapshots. Previously downloaded information remains readable while offline until the device learns about a revocation.

## Checks

```sh
./gradlew :core:test :app:testDebugUnitTest :app:lintDebug :app:assembleDebug
python3 scripts/check_contract.py ../api/openapi.json
# In Lorenzo, generate the current schema and check it:
mise run //apps/inventory-mobile:check-schema
```

Repository tests cover non-blocking local note persistence, logout during a request, replay after a failed reader write, and retaining permanently rejected drafts. HTTP tests exercise real requests against MockWebServer: roster deduplication, locale selection, unknown fields, zero values, actual inventory route, note pagination, stable note IDs/private defaults/reader calls, error parsing and redirect credential protection. No account token is needed. A real-account smoke test remains necessary to verify your character roster and notes against production; automated tests never write to production.
