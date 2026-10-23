# 0332 - Lorenzo Maps: a static app for Locations and, later, Maps

Status: accepted with the maintainer on 2026-10-23; RFC 0048 slices 1 and 4 onward.

## Decision

`apps/maps`, "Lorenzo Maps", is a static Astro app (`output: 'static'`, plain TypeScript, no
component framework, ADR 0004) in the shape of Lorenzo Calendars and Lorenzo Sessions. It uses the
shared page frame (`packages/app-shell`), the brand base, the typed API client, the read cache
(`packages/read-cache`) and the app-link registry (ADR 0273), signs in with Authgear as its own
public single-page-app client, and holds no durable private cache. It is desktop only for now: no
phone layout, no touch tuning, no offline grant. Bench integration is deferred.

The first slice shows a library's Locations and nothing else: a library switcher and sign-in from
the shell, a list with name search, a tree of roots with their parts, a Location page, and, for
those with authoring standing (ADR 0330), create, rename, re-parent, stack order and a "visible to
everyone" switch. Hierarchy lines say "in" or "within". Hidden Locations are absent, with no
placeholder and no count of what is missing. Routes accept ids or slugs and generate slugs where
they exist. A Map view arrives in later slices of RFC 0048 and draws with a hand-written SVG
renderer in its own framework-free package.

Hosting: a Cloudflare Pages project `lorenzo-maps` (Git integration, no workflow), the production
origin added to the API's `CORS_ALLOWED_ORIGINS`, an Authgear client with
`https://lorenzo-maps.pages.dev/auth/redirect/` and a local development redirect, and the
`/app-links` registry entries `location` and `location_by_slug` plus an app entry `maps`
(`MAPS_URL`). The setup steps live in `docs/operations/maps-setup.md`. The `app:maps` label is
created in the scaffolding pull request and applied to it and to its tracking issue.

CI declares the app as a node that depends on the API client, with a real-API end-to-end suite on
launcher ports of its own (the `test-e2e` convention), discovered like the other apps. The app is
listed in `AGENTS.md`, the README and the domain documents in the same pull request.

## Validation and delivery

The scaffold lands with slice 1 in one vertical pull request. Desktop and dark mode are checked in
a browser against the real API: sign-in, an empty library, create, nested Locations, re-parent,
a restricted Location seen as a player (absent) and as a GM (present), and the error states.

## Excluded

A phone layout, offline use, an installable app shell, placing entries at Locations (slice 2),
maps and drawing (slice 4 onward), the Bench embedding.
