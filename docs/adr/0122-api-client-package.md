# 0122 - `@lorenzo/api-client`: one typed API client for loot-bot and inventory-web

Status: accepted

## Context

`apps/loot-bot` and `apps/inventory-web` both talk to `apps/api` through a client typed against its OpenAPI schema ([ADR 0050](0050-loot-bot-stack-linking-and-isolation.md), [ADR 0091](0091-inventory-web-typed-api-client.md)). Each app keeps its own copy of everything that pattern needs:

- **The generated schema.** `apps/loot-bot/src/lorenzo-schema.d.ts` and `apps/inventory-web/src/lib/lorenzo-schema.d.ts` are byte-identical, 17,022 lines each.
- **The error path.** Each app has its own error class (`LorenzoApiError`, `ApiError`) with the same two fields, and the same permissive `zod` parse of RFC 9457 problem details.
- **The drift check.** CI's `client-drift` job fails when loot-bot's copy falls behind `apps/api`. Nothing checks inventory-web's copy, the gap ADR 0091 named and left open.

Every change to `apps/api`'s routes or schemas means regenerating both copies by hand. RFC 0030 (carrying, holding, binding, and capacity, proposed alongside this ADR on its own branch) will change them in several slices, each consumed by both apps.

Lorenzo's architecture draws a line this package has to respect: the API is the source of truth, and every client is a narrower view onto it ([docs/architecture/overview.md](../architecture/overview.md), [docs/domain/client-views.md](../domain/client-views.md)). A shared client that also decided things, such as whether an item may move or who may give it away, would be a second implementation of the API's rules in another language. It would drift the way any second implementation does.

## Decision

A new workspace package, **`packages/api-client`** (`@lorenzo/api-client`), holds what both apps need to talk to the API, and nothing else. loot-bot and inventory-web depend on it with `workspace:*` and drop their own copies.

### What it holds

- **The schema.** One generated `src/schema.d.ts`, from `apps/api/openapi.json` (`mise run //apps/api:openapi-schema`, unchanged). The package exports `paths`, `components`, and a `Schema<Name>` shorthand for `components['schemas'][Name]`.
- **The client.** `createLorenzoClient({ baseUrl, getAccessToken? })` returns an `openapi-fetch` client. Given `getAccessToken`, it adds the bearer token to every request and refuses up front with a 401 when there isn't one, inventory-web's current middleware. Without it, callers pass their own `Authorization` header per request, as loot-bot does: it acts for many users, each with their own token.
- **Errors.** One `LorenzoApiError` (`status`, `problemType`, plus the problem body's own extension fields), the problem-detail parse, and `unwrap()`, which turns an `openapi-fetch` result into its data or a thrown `LorenzoApiError`.
- **Small protocol helpers.** `fetchAllPages()` and `MAX_PAGE_SIZE` (ADR 0020's pagination), and `etagOf()`, which reads the `ETag` a response carried for a later `If-Match` ([ADR 0042](0042-concurrency-token-on-reads.md)).

### What stays out

- **Rules.** Whether a move, give, or split is allowed is the API's answer. When RFC 0030's slices add refusals with their own problem types, the package gains their types, so each app has to handle every kind, but never the logic that produces them.
- **App-shaped data.** loot-bot's `OwnedItem`, `ControlledCharacter`, and its per-command wrapper methods stay in loot-bot. inventory-web's `lib/types.ts` aliases stay in inventory-web, re-pointed at the package's types.
- **Presentation.** Stat labels, Discord formatting, and web markup stay with the surface that shows them.
- **Browser-only helpers.** inventory-web's `blobUrl()` depends on its own token and `URL.createObjectURL`, so it stays.

### How it's built and consumed

- **Source-only, like `@lorenzo/lorenzoscript`** ([ADR 0100](0100-lorenzoscript-core-parser-and-renderer.md)). Its `exports` point at `src/index.ts`; there is no build step. inventory-web's Vite build compiles it as it already compiles `lorenzoscript`.
- **loot-bot bundles it.** loot-bot's `tsup` skips everything in `node_modules`, so `@lorenzo/api-client` is listed under `noExternal` and ends up inside `dist/`. Its own dependencies (`openapi-fetch`, `zod`) are already loot-bot's, at the same versions. loot-bot's `Dockerfile` copies `packages/` into the build stage alongside `apps/`.
- **Deploys follow the package.** `deploy-loot-bot.yml` also triggers on `packages/api-client/**`. inventory-web's Cloudflare Pages build watch paths gain the packages it consumes. `lorenzoscript`, `lorenzoscript-editor`, and `brand` were already missing from them, so a change there never redeployed the site. [docs/operations/deployment-setup.md](../operations/deployment-setup.md) says so.
- **One drift check.** The package owns `generate` and `check` mise tasks. CI's `client-drift` job runs the package's `check` instead of loot-bot's, so one job now covers both consumers.
- **The usual package plumbing** ([docs/guides/adding-a-package.md](../guides/adding-a-package.md)): its own `mise.toml`, an entry in the root `mise.toml`'s `config_roots`, and its own release-please component.

## Not in scope

- **`apps/account-hub`.** It still has its own hand-written `apiFetch`, and moving it onto a typed client means rewriting every call, as ADR 0091 did for inventory-web. It's tracked as its own follow-up issue.
- **A higher-level SDK.** One method per endpoint on top of the typed client would mostly re-state `paths`, and it's where app-specific shapes would start to collect.
- **Publishing to npm.** It's consumed inside this monorepo only, like `@lorenzo/brand`.

## Consequences

- An `apps/api` schema change is regenerated once, in one place, and CI catches a stale copy for both apps, not just loot-bot.
- Two error classes become one. Code that caught `ApiError` in inventory-web or `LorenzoApiError` in loot-bot catches `LorenzoApiError` from the package.
- loot-bot's image build and deploy now depend on a directory outside `apps/loot-bot`. That's the cost of the shared source, and the `Dockerfile`, the deploy workflow's paths, and the Pages watch paths all have to name it.
- Rules stay server-side: a client that wants to know whether something is allowed asks the API, or reads a field the API computed. The package gives it no other way.
