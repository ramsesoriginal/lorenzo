# Lorenzo Writing setup

Status: unconfigured. The default `https://lorenzo-writing.pages.dev` address is a placeholder,
not evidence that a Pages project or Authgear client exists. RFC 0047, ADRs 0327–0329.

1. Create a separate Authgear SPA client using refresh-token sessions. Register the exact
   authorized redirect `https://lorenzo-writing.pages.dev/auth/redirect/` (including its trailing
   slash), the site's origin, and the local `http://localhost:4327/auth/redirect/` when needed.
2. Create a Cloudflare Pages project with this repository's Git integration, production branch
   `main`, build `pnpm install --frozen-lockfile && pnpm --filter @lorenzo/writing build`, and
   output `apps/writing/dist`. Use the repository's Node and pnpm versions.
3. Set `PUBLIC_API_BASE_URL`, `PUBLIC_AUTHGEAR_ENDPOINT` and this app's
   `PUBLIC_AUTHGEAR_CLIENT_ID` in the Pages build environment. Branding is bundled locally;
   `PUBLIC_BRANDING_CSS_URL` is optional.
4. Add the exact site origin to the API's `CORS_ALLOWED_ORIGINS` and set `WRITING_URL` if the
   address differs from the placeholder. The registry's `manuscript` template uses tenant and
   entry identity; other apps should get the address from `GET /app-links`.
5. Verify sign-in/sign-out, an Author in both library and repository, text and image autosave,
   reload recovery, a conflicting save, saved revisions and access revocation before announcing
   availability. Do not reuse a production database for the browser tests.

No deployment is performed by scaffolding the app or opening its PR.
