# apps/

One directory per deployable application, named by purpose, not type. There is no fixed slot per "kind" of app — there can be one or many web frontends, multiple mobile apps, one or more Discord bots, side by side.

See [ADR 0007](../docs/adr/0007-apps-layout-and-multiplicity.md) for the reasoning and [docs/guides/adding-an-app.md](../docs/guides/adding-an-app.md) for how to add one.

- [`api`](api) — backend REST API. Infrastructure, plus the full domain model, a full read/write REST API, and Authgear-backed auth.
- [`loot-bot`](loot-bot) — Discord bot. Account linking, self-service inventory viewing/managing, loot-splitting, GM loot drops with claims, and item awarding — see its own README for the full command list.
- [`inventory-web`](inventory-web) — static Astro frontend. GM item catalog/instance management, kanban-style container board.
- [`inventory-mobile`](inventory-mobile) — Lorenzo Inventory, a native Kotlin/Compose Android app. Read character inventories and item details, use encrypted offline snapshots and create private notes with durable synchronization ([ADR 0291](../docs/adr/0291-inventory-mobile-native-android-app.md)); install a locally built APK.
- [`account-hub`](account-hub) — static Astro frontend. A user's own account: profile, notifications, tenant/campaign roster and admin, character/being management.
- [`beings`](beings) — static Astro frontend, "Lorenzo Beings". Characters and NPCs: a filtered list, a page for each, notes in four audiences, editing, stats, creating and handing over.
- [`bench`](bench) — Lorenzo Bench, the static repository authoring workbench: entry editing, text, stats, formulas, pictures, ancestry and compare views; persistent offline work is a later slice of RFC 0039.
- [`brand`](brand) — shared CSS, fonts, icon atlas and a static brand preview, bundled by consumers through `packages/brand`.
- [`cli`](cli) - the `lorenzo` command line (Python). Talks to the API: creates and seeds a repository tenant, imports MPMB standard items into it, hands packs out, publishes repositories, copies and updates them, and imports/exports LorenzoLedger inventories (RFC 0025, ADR 0159, 0193, 0226). Install it with `uv tool install "git+https://github.com/ramsesoriginal/lorenzo#subdirectory=apps/cli"`.
