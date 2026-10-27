# Setting up Lorenzo Maps for hosting

[Lorenzo Maps](../../apps/maps/README.md) is a static Astro app ([ADR 0332](../adr/0332-lorenzo-maps-the-app.md)). Its planned production address is `https://lorenzo-maps.pages.dev`, the default of `MAPS_URL` in the API's settings. It follows the other static apps: Cloudflare Git integration builds from `main`, without a separate GitHub deployment workflow. See [deployment setup](deployment-setup.md) for shared Authgear, Cloudflare and CORS details, and [Lorenzo Sessions hosting](sessions-setup.md), which this procedure mirrors.

## Pages

Create a Pages project connected to `ramsesoriginal/lorenzo`, named `lorenzo-maps`, production branch `main`. Set the root to `apps/maps`, output to `dist`, and the `NODE_VERSION` environment variable to the Node major in the root `mise.toml` (currently 26). Build with:

```bash
npm install --global corepack@latest && corepack enable && pnpm install --frozen-lockfile && pnpm run build
```

`pnpm run build` builds `@lorenzo/brand`, copies its files into `public/branding/` (`scripts/copy-branding.mjs`) and then runs `astro build`.

Watch `apps/maps/**`, `packages/api-client/**`, `packages/app-shell/**`, `packages/read-cache/**`, `packages/brand/**`, `apps/brand/**`, `pnpm-lock.yaml` and `tools/brand/**`.

## Authgear and public configuration

Create a public Single Page Application client named Lorenzo Maps in the existing Authgear project. Register these exact callback addresses, including their trailing slash (Cloudflare Pages redirects a bare `/auth/redirect` to the slash form):

- `https://lorenzo-maps.pages.dev/auth/redirect/`
- `http://127.0.0.1:4327/auth/redirect/`

Allow the respective origins as post-logout redirect addresses. Supply the Pages build's `PUBLIC_AUTHGEAR_ENDPOINT` and `PUBLIC_AUTHGEAR_CLIENT_ID`; optionally override `PUBLIC_API_BASE_URL` and `PUBLIC_BRANDING_CSS_URL` (see `apps/maps/.env.example`). These are public configuration, not client secrets, and no client secret belongs in a static build. Check the provider's current client limits in its console before creating another application.

## API and verification

Add the production origin to the API's existing space-separated `CORS_ALLOWED_ORIGINS` list and deploy the API through its normal workflow. The app registry already has the planned `https://lorenzo-maps.pages.dev` address; set the API/GitHub `MAPS_URL` variable for a different origin. Deployment passes an unset value through to the API's default. Preview origins need their own explicit CORS and callback authorization.

Call `GET /app-links` and confirm that `apps.maps.url` is the address you deployed and that the `location`, `location_by_slug`, `map` and `map_by_slug` links point at it.

Open the app and sign in as a GM. Add a top-level Location and a Location inside it, keep one restricted, and move one. Check as a player that a restricted Location does not appear, and that a visible Location inside a restricted one shows directly under the nearest Location the player can see. Check that logout works. Without `PUBLIC_AUTHGEAR_ENDPOINT` and `PUBLIC_AUTHGEAR_CLIENT_ID` the app reports that Authgear is not configured.

Make a Map with `POST /tenants/{id}/maps`, draw a Location on it with `PUT /tenants/{id}/maps/{map_id}/placements/{entry_id}`, and open the Map from the Maps page: the place is drawn, selecting it names it, and a player sees only the places they may see.

As a GM, choose *Edit this map* and draw a pin for a Location and an area for a new one, change a role, drag a handle, undo, and place the children of an area; check that a player sees the same Map with no tools, and that *Look* and *Legend* work. The API must be the version with `POST .../placements/batch` and the Map's theme name before the app is deployed.

No setting data, Location, Map or axis is seeded during deployment.
