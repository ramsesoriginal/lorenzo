# 0273 - The registry of app links

Status: accepted

## Context

The apps link to each other: a notification leads into the account hub, an item in a text opens in inventory-web, a being in Lorenzo Beings, a character's board in inventory-web again, the device-code flow sends a person to the hub. Each app learned the others' addresses from a variable of its own: inventory-web `PUBLIC_ACCOUNT_HUB_URL`, account-hub `PUBLIC_BEINGS_BASE_URL`, beings `PUBLIC_INVENTORY_WEB_BASE_URL`, and the API `ACCOUNT_HUB_URL` for the verification URI of the personal-access-token device flow. Moving an app, or adding a fifth, meant editing the build settings of every app that points at it, and each app also knew the URL *shape* of the others (`/item/?tenant=&id=`, `/board/?tenant=&character=`, `/being/?tenant=&id=`).

## Decision

**The API is the one place that says where the apps live and what the default links between them are.** `GET /app-links`:

```json
{
  "apps":  { "account_hub": {"url": "..."}, "inventory_web": {...}, "beings": {...}, "bench": {...} },
  "links": { "item": "https://.../item/?tenant={tenant}&id={id}", "...": "..." }
}
```

- **Public**: no authentication; it names no library and no person. It answers `Cache-Control: public, max-age=300`, and carries the CORS headers of every other route ([ADR 0048](0048-cors-configuration.md)).
- **Templates, not functions**: a link is a URL with named placeholders (`{tenant}`, `{id}`, `{slug}`) that the client fills in, percent-encoding each value. The default shapes are exactly the ones the apps build by hand today, so existing links keep working: `item` and `item_by_slug` (inventory-web's item page for an item or inventory item), `inventory` and `board` (a character's board), `being` and `being_by_slug` (a being's page in Lorenzo Beings), `notifications` and `notification` (the hub's notifications page, and where a notification leads when it names no target), `repository` and `studio` (the hub's pages), `device` (the hub's device page).
- **Source: API settings read from environment variables**, in one group: `ACCOUNT_HUB_URL`, `INVENTORY_WEB_URL`, `BEINGS_URL`, `BENCH_URL` (defaults: the official `https://lorenzo-<app>.pages.dev` addresses; an empty value means the default, since an unset GitHub variable reaches the container as an empty string), and `APP_LINK_TEMPLATES` for single links (space-separated `name=template` pairs, no commas or JSON, for the reason [ADR 0048](0048-cors-configuration.md)'s addendum gives). Trailing slashes are stripped. `deploy-api.yml` passes them through; [deployment-setup.md](../operations/deployment-setup.md) documents them.
- **A pure module**, `lorenzo_api/app_links.py`, builds the document from `Settings`, and offers `account_hub_url(settings)` and `device_url(settings)` for API code that needs an address itself. The personal-access-token device flow (its own branch) reads its verification URI through `device_url` instead of a variable of its own.
- **Clients**: `getAppLinks(baseUrl)` in `packages/api-client` fetches once and keeps the answer in memory (a failure is not kept), and `fill(template, params)` fills a template, URL-encoding values.
- **The fallback rule for clients**: ask the registry first; use the app's own address variable only if the registry cannot be reached or lacks the entry. Those variables stay, as fallbacks, so a deployment with an API that predates this endpoint, or an offline developer, still works.

## Why not a database

Nothing about it is per library or per person, an operator changes it perhaps once a year, and the API already restarts on a deploy that changes any setting. A table would need an admin surface, migrations and a seed before it could say what an environment variable says today. When an admin page for it is wanted, it can move into the database behind the same endpoint and the same `app_links` module; clients will not notice.

## Alternatives considered

- **Each app keeps its own variables** (the status quo): every move edits several deployments, and a typo in one app's variable silently breaks only that app's links.
- **A static `app-links.json` served by one of the Pages projects**: a fifth thing to deploy, no CORS guarantee, and no link to the API's own need for the hub address.
- **Finished URLs, not templates**: the client would still have to know each shape, or ask for one URL per entity.

## Consequences

- The API's OpenAPI schema, the typed client's `schema.d.ts` and the CLI's models gain `AppLinksOut`.
- The apps (inventory-web, account-hub, Lorenzo Beings) adopt the registry in their own slices, with their address variables as fallbacks.
- The hover-preview templates that the v1.0 checklist's "Link registry plus hover preview templates" row also names are a different thing (ADR 0264); the "link registry" half is this ADR.
- A new link is one line in `_DEFAULTS` in `app_links.py` and one in the list in deployment-setup.md.
