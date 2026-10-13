# 0211 - Bench: sign-in and the repository picker

Status: accepted, decided with the maintainer on 2026-10-09. Slice B2 of [RFC 0039](../rfcs/0039-bench-authoring-offline-and-extensibility.md). Builds on [ADR 0210](0210-bench-app-stack-and-workbench-shell.md) and [ADR 0071](0071-account-hub-stack-auth-deploy.md).

## Context

Bench's shell ran on stub data with no sign-in. The Authgear application and the Cloudflare Pages project (`lorenzo-bench`) now exist, so the shell can know who is using it and which repository they are in. Opening a repository's entries is B3; this slice stops at choosing one.

## Decision

- **Its own Authgear Single Page Application client**, public and PKCE, as the other static apps: `PUBLIC_AUTHGEAR_ENDPOINT` and `PUBLIC_AUTHGEAR_CLIENT_ID`, and an optional `PUBLIC_API_BASE_URL` that defaults to the deployed API. Redirect path `/auth/redirect/`, with the trailing slash, for the reason in `apps/inventory-web`'s `auth.ts`. Session type `refresh_token`.
- **The same page works without sign-in.** With no Authgear variables the title bar says it is sample data and nothing else changes; signed out, the workbench is still shown and the title bar offers Sign in. The SDK and the API client are loaded only when sign-in is configured.
- **The picker lists the repositories a person authors**: tenants of kind `repository` where their role is Owner, Organizer or Author ("pinned = every repository you author", RFC 0039). A library, or a repository they only read, is not listed. The API's schema does not have the Author role yet ([RFC 0040](../rfcs/0040-authors-and-invites.md)), so roles are compared as strings.
- **The repository last chosen is remembered per person** on the device and is forgotten at sign-out. Layout, which is not about a person, is kept.
- **The entries are still sample entries** until B3. The title bar says so, so a signed-in person does not take them for the repository's.
- **Tests**: the pure choice of repositories is unit tested; the browser tests build a second copy of the page with sign-in configured against an Authgear that does not exist, answer its discovery request, and check that Sign in goes to the authorize endpoint with this client, PKCE, and the slash-form redirect. A real login against Authgear and the API is not covered in CI.

## Consequences

- Nothing in Bench calls the API except reading `/me` and the tenant list.
- What a first real login settles, as for the CLI: whether this client is given a refresh token, and for how long (RFC 0039 open question).
- `docs/operations/deployment-setup.md` has the Bench section: the Authgear application, the Pages project and its variables.
