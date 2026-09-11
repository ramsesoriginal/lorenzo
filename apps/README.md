# apps/

One directory per deployable application, named by purpose, not type. There is no fixed slot per "kind" of app — there can be one or many web frontends, multiple mobile apps, one or more Discord bots, side by side.

See [ADR 0007](../docs/adr/0007-apps-layout-and-multiplicity.md) for the reasoning and [docs/guides/adding-an-app.md](../docs/guides/adding-an-app.md) for how to add one.

- [`api`](api) — backend REST API. Infrastructure, plus the full domain model, a read-only REST API, and Authgear-backed auth.
- [`loot-bot`](loot-bot) — Discord bot. Links a Discord user to their Lorenzo identity, then shows the item instances their characters own.
