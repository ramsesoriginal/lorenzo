# 0161 - `lorenzo api`: an authenticated request, for scripts

Status: accepted

Follow-up to [ADR 0137](0137-lorenzo-cli-app-python-client-and-auth.md). Part of the set decided together on 2026-10-03 ([ADR 0153](0153-lorenzo-version.md)).

## Context

[RFC 0025](../rfcs/0025-lorenzo-cli-mpmb-item-importer.md) named scripts and tools like Claude Code as users of this CLI, and the API has about 150 routes, of which the CLI wraps nineteen. Each wrapped route took a command, tests and an ADR, and many will never be worth one. Meanwhile the hard parts of calling the API from a shell are exactly what the CLI already has: finding a token, renewing it after a `401`, retrying a safe request that dropped, sending `If-Match`, and not sending the token to the wrong place. Without a way to use them, a script falls back to `curl` and a copied token, which is what `docs/operations/exporting-your-tenant.md` does today.

## Decision

```bash
lorenzo api METHOD PATH [--data JSON|@FILE|-] [--query KEY=VALUE]... [--if-match ETAG]
                        [--include] [--paginate] [--raw]
```

One authenticated request to the API the CLI is configured for, and its answer printed.

- **`METHOD`** is `GET`, `POST`, `PUT`, `PATCH` or `DELETE`, in any case.
- **`PATH`** starts with `/`, as in `/tenants` or `/tenants/{id}/stat-groups`. It may carry its own query string; `--query` adds to it.
- **It takes a path, never a URL.** A `PATH` with a scheme or a host (`https://…`, `//host/…`) is refused before any request. The CLI sends the person's token to the API they named ([ADR 0137](0137-lorenzo-cli-app-python-client-and-auth.md), [0157](0157-lorenzo-remembers-the-api-url-issuer-and-client-id.md)) and to nowhere else, and this command is the one place a typo or a pasted link could change that.
- **`--data`** is the request body: JSON text, `@file` to read a file, or `-` to read stdin. It must parse as JSON before anything is sent, and it is only allowed for `POST`, `PUT` and `PATCH`.
- **`--if-match`** sends `If-Match`, for the routes that guard writes with an ETag ([ADR 0042](0042-concurrency-token-on-reads.md)). `--include` is how to see the `ETag` that a read returned.
- **It uses the client the other commands use**, so a `401` renews the token once and retries, `GET`, `PUT` and `DELETE` retry a dropped connection and a `502`, `503` or `504`, and `POST` and `PATCH` never do (no idempotency key, [ADR 0137](0137-lorenzo-cli-app-python-client-and-auth.md)).

### What it prints

- **The body goes to stdout**, pretty-printed if it is JSON (`--raw` leaves it exactly as received), so `lorenzo api GET /tenants | jq` works.
- **`--include`** first prints the status line and the response headers.
- **A refusal is still printed**, as the API sent it (its `application/problem+json` body, on stdout), and a one-line summary goes to stderr: the status and its `detail`. **The exit code is 0 for a 2xx answer and 1 for anything else**, 4xx and 5xx alike. So a script can both branch on the exit code and read the problem.
- **A connection that can't be made** is the CLI's usual one-line error, exit 1.

### Paging

Every list in the API is a page (`items`, `total`, `page`, `size`, `pages`). `--paginate`, for `GET` only, walks them all (`size=100`) and prints one JSON array of the items. A response that isn't a page is printed as it is. It exists because the export runbook's `walk` helper is the thing every script would otherwise rewrite.

## Not in scope

- **Typed commands for each route.** This is the escape hatch, not the plan; a route that earns a command still gets one, with its own ADR.
- **`HEAD` and `OPTIONS`**, and **custom headers** other than `If-Match`. Nothing here needs them.
- **Anything that bypasses the API's own checks.** The request is the person's own, under their own token, and `apps/api` decides.
- **Remembering anything** about the request: no history, no saved calls.

## Consequences

- A script or an assistant can do anything the API allows with the login that already works, without a token pasted into a shell history.
- The CLI becomes a way to make a destructive request with one line. That is true of `curl` too, and the API's own authorization is what stands between a person and a route they may not use.
- The transport gains one lower-level method that returns the raw response; the typed `call` is built on it, so the retry and renewal rules stay in one place.
