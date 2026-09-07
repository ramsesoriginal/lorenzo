# Architecture overview

## Components

Every deployable app lives under `apps/`, one directory per app, named by purpose rather than type — see [ADR 0007](../adr/0007-apps-layout-and-multiplicity.md). None exist yet.

| Component type | Role | Multiplicity |
|---|---|---|
| Backend API | Source of truth. Multi-tenant REST API over PostgreSQL. | One (shared source of truth) |
| Web frontend(s) | Static UI for GMs/players (zero-JS by default). | One or many |
| Discord bot(s) | Talks to the API — e.g. loot/inventory. | At least one, possibly more |
| Mobile app(s) | Talks to the API — narrower, audience-specific views. | Possibly more than one |

Everything other than the backend API is a *view* onto it — narrower, audience-specific slices of the same data, not a separate source of truth. See the [system context diagram](diagrams/system-context.md).

## Domain shape (why the data model will look the way it does)

Lorenzo's job is tracking, for game masters/authors: **where** something is (physical location, position in space, sphere, plane, parallel timeline, or multiverse — several independent, not-always-linear coordinate systems at once), **who knows what** (knowledge is per-character/per-point-in-time, not global), and **who can see what** (every piece of text/stats is split by audience: GM-only, everyone, a subset of players, player-authored).

A **repository** is a reusable setting (a published campaign setting, a homebrew world, an entire multiverse) that a game can draw on; a game/campaign can use zero, one, or several repositories at once, and several campaigns can share one repository's live state or run independent instances of it.

None of this is modeled yet — no schema, no ADR/RFC for the entity design. That's real design work for when the backend API is actually scoped, not something to improvise into this foundation pass.

## Cross-cutting concerns (intentions, not yet built)

- **Multi-tenancy**: [ADR 0002](../adr/0002-multi-tenancy-shared-schema-rls.md) — shared schema + PostgreSQL row-level security.
- **Observability**: health/readiness/metrics endpoints and structured logs are meant to exist from the backend API's first commit, not added later.
- **Auth**: a real identity provider is an open, separate decision — not designed speculatively here.

## Roadmap

Tracked as [GitHub issues/milestones](https://github.com/ramsesoriginal/lorenzo/issues) once there's something to track. Immediate next step: scope and scaffold the first real app — most likely the backend API, since everything else depends on it.
