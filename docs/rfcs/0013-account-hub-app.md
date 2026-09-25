# RFC: `apps/account-hub` — a user's own account surface

Status: accepted — landed in `apps/account-hub` 1.0.0: the Foundation sub-slice as [ADR 0071](../adr/0071-account-hub-stack-auth-deploy.md), the other five directly against this RFC with no ADR of their own. The Beings sub-slice was scoped down in conversation when built: tenant-scoped rather than per campaign (a being has no campaign of its own) and name-only list/create/rename — the key/value stat editor in sub-slice 6 is not built. The notify-only `apps/loot-bot` push layer deferred below later landed separately, as [ADR 0095](../adr/0095-loot-bot-notification-dms.md)

## Context

Every client built so far is scoped to one narrow job against a specific slice of the domain: `apps/loot-bot` is inventory/loot mechanics, `apps/inventory-web` is inventory viewing/management. Nothing yet lets a user manage themselves — their own profile, their own notifications, which tenants and campaigns they actually have standing in — independent of any one tenant or campaign. That's a real gap: `GET /me` (ADR 0023), the profile fields (ADR 0060), the notification inbox (ADR 0058/0059/0061), and tenant/campaign read access (ADR 0030/0031) all exist server-side with nothing surfacing them.

This gap was scoped through a structured, adversarial debate across five independently-researched client shapes (a PWA, a cross-platform mobile app, an extension to `apps/loot-bot`, a Tauri desktop app, and a conversational/LLM front-end), each defended and then cross-examined against the other four. The debate converged: a static web app forking `apps/inventory-web`'s already-working Astro + `@authgear/web` + Cloudflare Pages pattern is the right primary surface, at far lower cost and risk than any alternative, because that pattern is real, working code today rather than a new integration to prove out. The mobile, desktop, and conversational options each self-eliminated under their own advocates' cross-examination (see Consequences for what's explicitly deferred, not rejected, from that debate).

Per [docs/domain/client-views.md](../domain/client-views.md) and [ADR 0007](../adr/0007-apps-layout-and-multiplicity.md), this project generally prefers multiple narrow, audience-specific apps over one do-everything frontend. This app is a deliberate exception to that default, not a departure from it: its subject is inherently the caller's *own* account — which by construction spans "I'm a GM in campaign A" and "I'm a player in campaign B" for the same person at once. Splitting it into a GM-facing and a player-facing app would duplicate the profile/notifications/tenant-listing surface in both, for no audience-isolation benefit, since the data being shown is already scoped to the caller alone by the API's own authorization.

## Decision

Build **`apps/account-hub`**, a new static Astro web app, covering six capabilities, all going through the existing REST API and its existing authorization — this app never re-implements or second-guesses auth, only surfaces the API's own 403/404s:

1. View and edit the caller's own profile (`nickname`, `display_name`, `pronouns`, `bio`, `locales`, `user_color`, profile picture) — `GET`/`PATCH /me`, `PUT`/`DELETE /me/picture`.
2. View and mark-read the caller's notification inbox — `GET /me/notifications`, `POST /me/notifications/{id}/read`.
3. See which tenants the caller belongs to and their role in each — `GET /me`'s membership list.
4. See which campaigns the caller has access to, as player and/or GM — `GET /me`'s player/GM listings plus tenant/campaign read endpoints.
5. If a player in a campaign: create and manage their own character(s) in it — the existing character CRUD surface (ADR 0036).
6. If a GM in a campaign: create and manage "beings" — NPCs and any other non-player entity, with stats — the existing entity/stat CRUD surface (ADR 0037/0039 and the generic entity model).

### Sub-slices, smallest first

Each slice is its own vertical, tested end to end against the real API before the next starts, matching this project's established process (RFC 0001/0002's own "small sub-slices, not a broad partial implementation"):

1. **Foundation**: app skeleton forked from `apps/inventory-web` (Astro config, `mise.toml`, Biome/tsconfig/Prettier, brand assets/layout/styles), the Authgear login/logout/session round-trip, and a bare `GET /me` proving the whole pipeline — no new UI beyond proving auth works, mirroring `apps/inventory-web/src/pages/debug/me.astro`'s own precedent.
2. **Profile**: view/edit all six self-editable fields, picture upload/display.
3. **Notifications**: inbox list, mark-read, polling for freshness (no server push exists today — see Consequences).
4. **Tenants and campaigns**: read-only listing of both, with role/access shown per row.
5. **Characters**: list-mine, create, edit, for campaigns the caller plays in.
6. **Beings**: list, create, edit — GM-only, per campaign, including the open-ended key/value stat editor.

### What this RFC deliberately does not decide

Concrete technology choices (exact dependency versions, whether e2e testing needs a new tool this repo doesn't have yet, deploy workflow specifics) are ADR-shaped decisions, made and merged one at a time as each slice above is actually built — not pre-decided here. This RFC fixes *scope*, not implementation.

## Consequences

- A new `apps/account-hub` label, `mise.toml` task contract, workspace/release-please/Dependabot/pre-commit registrations, and deploy workflow are needed per [docs/guides/adding-an-app.md](../guides/adding-an-app.md) — tracked as part of the Foundation slice's own ADR, not this RFC.
- **Explicitly deferred, not rejected**, per the debate that produced this RFC — named here so they aren't lost, per this project's own standing rule that anything beyond the current sub-slice is scoped only once actually picked up:
  - A notify-only push layer added to `apps/loot-bot` (DMing linked users when they have new notifications, deep-linking back into this app) — the strongest secondary idea from the debate, genuinely additive and low-risk, but a separate app's own follow-on slice, not this RFC's to design.
  - Any form of AI-assisted/conversational creation flow (e.g. a "chat to create" mode for being-authoring) — floated in the debate as a possible future feature *inside* whatever app wins, never as a standalone app; not scoped until real usage shows the plain form is genuinely the bottleneck.
  - Real push notifications (Web Push) from this app itself — needs new `apps/api` surface (a subscription table + RLS, VAPID) this RFC does not request; v1 ships with polling only, which fully satisfies today's API (an in-app-only inbox, no server-side delivery channel).
- This is the first Astro app in the monorepo built for a *personal, cross-tenant* view rather than a single tenant's inventory board — `apps/inventory-web`'s API-client/types/auth modules are reused, but its actual pages/domain types are not, since the data shape here is different (the caller's own account, not one tenant's inventory).
