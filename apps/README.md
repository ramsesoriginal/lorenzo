# apps/

One directory per deployable application, named by purpose, not type. There is no fixed slot per "kind" of app — there can be one or many web frontends, multiple mobile apps, one or more Discord bots, side by side.

See [ADR 0007](../docs/adr/0007-apps-layout-and-multiplicity.md) for the reasoning and [docs/guides/adding-an-app.md](../docs/guides/adding-an-app.md) for how to add one.

- [`api`](api) — backend REST API. Infrastructure, plus the full domain model, a full read/write REST API, and Authgear-backed auth.
- [`loot-bot`](loot-bot) — Discord bot. Account linking, self-service inventory viewing/managing, loot-splitting, GM loot drops with claims, and item awarding — see its own README for the full command list.
- [`inventory-web`](inventory-web) — static Astro frontend. GM item catalog and instance management, a kanban-style container board, notes, handing items over and a public catalog for players.
- [`inventory-mobile`](inventory-mobile) — Lorenzo Inventory, a native Kotlin/Compose Android app. Read character inventories and item details, use encrypted offline snapshots and create private notes with durable synchronization ([ADR 0291](../docs/adr/0291-inventory-mobile-native-android-app.md)); install a locally built APK.
- [`inventory-ios`](inventory-ios) — SwiftUI inventory companion, encrypted offline notes and free macOS CI/AltStore testing ([ADR 0307](../docs/adr/0307-inventory-ios-and-altstore-testing.md)).
- [`account-hub`](account-hub) — static Astro frontend. A user's own account: profile, notifications, tenant/campaign roster and admin, character/being management.
- [`beings`](beings) — static Astro frontend, "Lorenzo Beings". Characters and NPCs: a filtered list, a page for each, notes in four audiences, editing, stats, creating and handing over.
- [`bench`](bench) — Lorenzo Bench, the static repository authoring workbench: entry editing, text, stats, formulas, pictures, ancestry and compare views; persistent offline work is a later slice of RFC 0039.
- [`calendars`](calendars) — static Astro frontend, "Lorenzo Calendars". Authored calendars with computed years, weeks and moons, explicit period notes, minimal Events and Fact dates, recurring observances and the Events page; import goes through the CLI ([ADR 0308](../docs/adr/0308-authored-calendars-and-calculation.md) to [0315](../docs/adr/0315-reader-scoped-event-order-and-sharing.md)).
- [`sessions`](sessions) — static Astro frontend, "Lorenzo Sessions". Campaign Sessions, reusable Scenes and their appearances, rosters, preparation and played order, and notes for GMs and players ([RFC 0046](../docs/rfcs/0046-sessions-scenes-and-lived-order.md), [ADR 0317](../docs/adr/0317-sessions-scenes-and-collaborative-planning.md) to [0319](../docs/adr/0319-personal-lived-order-as-event-evidence.md)).
- [`writing`](writing) — Lorenzo Writing: standalone Scene manuscripts with LorenzoScript, ordered pictures, autosave, browser recovery and saved revisions ([RFC 0047](../docs/rfcs/0047-lorenzo-writing.md), ADRs 0327–0329). Books, independent Editions and nested Chapters compose prose and pictures in an outline and continuous reading view (ADR 0341).
- [`brand`](brand) — shared CSS, fonts, icon atlas and a static brand preview, bundled by consumers through `packages/brand`.
- [`cli`](cli) - the `lorenzo` command line (Python). Talks to the API: creates and seeds a repository tenant, imports MPMB standard items into it, hands packs out, publishes repositories, copies and updates them, and imports/exports LorenzoLedger inventories (RFC 0025, ADR 0159, 0193, 0226). Install it with `uv tool install "git+https://github.com/ramsesoriginal/lorenzo#subdirectory=apps/cli"`.

Shared code lives under [`packages/`](../packages/README.md).
