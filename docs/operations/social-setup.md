# Setting up Lorenzo Social for hosting

[Lorenzo Social](../../apps/social/README.md) is a static Astro app ([ADR 0408](../adr/0408-lorenzo-social-the-app.md)). It follows the other static apps: Cloudflare Git integration builds from `main`, without a separate GitHub deployment workflow. See [deployment setup](deployment-setup.md) for the shared Authgear, Cloudflare and CORS details, and [Lorenzo Maps hosting](maps-setup.md), which this procedure mirrors. **The steps below are the maintainer's: nothing here is created by the pull request that adds the app.**

## Pages

Create a Pages project connected to `ramsesoriginal/lorenzo`, named `lorenzo-social`, production branch `main`. Set the root to `apps/social`, output to `dist`, and the `NODE_VERSION` environment variable to the Node major in the root `mise.toml`. Build with:

```bash
npm install --global corepack@latest && corepack enable && pnpm install --frozen-lockfile && pnpm run build
```

`pnpm run build` builds `@lorenzo/brand`, copies its files into `public/branding/` (`scripts/copy-branding.mjs`) and then runs `astro build`.

Build watch paths follow [the rule in the deployment setup](deployment-setup.md#build-watch-paths). For this app: `apps/social/**`, `apps/brand/**`, `packages/api-client/**`, `packages/app-shell/**`, `packages/brand/**`, `packages/entry-preview/**`, `packages/graph-renderer/**`, `packages/information-editor/**`, `packages/lorenzoscript/**`, `packages/lorenzoscript-editor/**`, `packages/period-picker/**`, `packages/read-cache/**` and `pnpm-lock.yaml`.

## Authgear and public configuration

Create a public Single Page Application client named Lorenzo Social in the existing Authgear project. Register these exact callback addresses, including their trailing slash (Cloudflare Pages redirects a bare `/auth/redirect` to the slash form):

- `https://lorenzo-social.pages.dev/auth/redirect/`
- `http://127.0.0.1:4329/auth/redirect/`

Allow the respective origins as post-logout redirect addresses. Supply the Pages build's `PUBLIC_AUTHGEAR_ENDPOINT` and `PUBLIC_AUTHGEAR_CLIENT_ID`; optionally override `PUBLIC_API_BASE_URL` and `PUBLIC_BRANDING_CSS_URL` (see `apps/social/.env.example`). These are public configuration, not client secrets, and no client secret belongs in a static build.

## API and verification

Add the production origin to the API's existing space-separated `CORS_ALLOWED_ORIGINS` list and deploy the API through its normal workflow. Preview origins need their own explicit CORS and callback authorization.

The app-link registry ([ADR 0273](../adr/0273-app-links-registry.md)) has the `social` address `https://lorenzo-social.pages.dev` and the links `relationship` and `social_web`. Set the API/GitHub `SOCIAL_URL` variable for a different origin; deployment passes an unset value through to the API's default, and a change needs a "Deploy API" run.

Open the app, sign in as a GM and make two beings or Locations, then a relationship between them: restricted, then opened to the library. Check as a player that a restricted relationship, and one whose end the player cannot see, are not listed. Check that logout works. Without `PUBLIC_AUTHGEAR_ENDPOINT` and `PUBLIC_AUTHGEAR_CLIENT_ID` the app reports that Authgear is not configured.

No relationship, type or standing is seeded during deployment.
