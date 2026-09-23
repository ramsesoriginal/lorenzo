# apps/

One directory per deployable application, named by purpose, not type. There is no fixed slot per "kind" of app — there can be one or many web frontends, multiple mobile apps, one or more Discord bots, side by side.

See [ADR 0007](../docs/adr/0007-apps-layout-and-multiplicity.md) for the reasoning and [docs/guides/adding-an-app.md](../docs/guides/adding-an-app.md) for how to add one.

- [`api`](api) — backend REST API. Infrastructure, plus the full domain model, a full read/write REST API, and Authgear-backed auth.
- [`loot-bot`](loot-bot) — Discord bot. Account linking, self-service inventory viewing/managing, loot-splitting, GM loot drops with claims, and item awarding — see its own README for the full command list.
- [`inventory-web`](inventory-web) — static Astro frontend. GM item catalog/instance management, kanban-style container board.
- [`account-hub`](account-hub) — static Astro frontend. A user's own account: profile, notifications, tenant/campaign roster and admin, character/being management.
