# Sessions hosting setup

Lorenzo Sessions is a static Astro app (ADR 0317), not deployed by opening its PR.

1. Create its Authgear web client with callback https://lorenzo-sessions.pages.dev/auth/redirect/
   (and local http://localhost:4326/auth/redirect/). Enable the same refresh-token/PKCE setup as Calendars.
2. Create Cloudflare Pages project lorenzo-sessions connected to this repository, production main.
   Build with the repository pnpm toolchain: pnpm --filter @lorenzo/sessions build; output apps/sessions/dist.
3. Set PUBLIC_API_BASE_URL, PUBLIC_AUTHGEAR_ENDPOINT and PUBLIC_AUTHGEAR_CLIENT_ID in Pages.
4. Allow the production and approved preview origins in the API CORS configuration.
5. Set SESSIONS_URL if the actual address differs from the planned fallback. Confirm GET /app-links.
6. Verify GM sign-in, Session creation, player restricted/shared notes and logout on desktop and phone.

No setting data or Session roster is seeded during deployment. Keep client secrets out of static builds.
