# Lorenzo web interfaces: design

The design guidelines for Lorenzo's web interfaces and a fresh design of each web app, worked out with the maintainer on clickable prototypes. This page holds the brief and the decision log. Nothing is decided until it is in the log.

Status: Phase 1 (principles and brief) in progress. No prototype is committed yet.

## Layout of this directory

- `web/` (this directory): the system. Brief, decision log, shell prototype, screens.
- `web/<app>/`: one directory per app design, in the order of the log below.
- [`../bench`](../bench/README.md) and [`../beings`](../beings/README.md) are earlier designs and are not changed by this work.

## Scope of the work

| App | Treatment |
| --- | --- |
| account-hub | New design |
| writing | New design |
| calendars and sessions | New design, together |
| maps | New design |
| beings | New design |
| inventory-web | Minimal redesign only |
| bench | No redesign. It stays its own thing; the system takes nothing from it unless the maintainer says so |

## Decision log

Each entry: what was decided, the options turned down, and the date.

### D1. Where the deliverables live (decided with the maintainer, 2026-11-04)

A `docs/design/web/` directory for the system and `docs/design/web/<app>/` per app. Turned down: `docs/design/<app>-v2/` per app.

### D2. Output form (decided with the maintainer, 2026-11-04)

Both: a design canvas for exploring alternatives and plain HTML and CSS linking `apps/brand` in place for the clickable shell and the chosen app prototypes. Turned down: canvas only; HTML only.

### D3. Order of the apps (decided with the maintainer, 2026-11-04)

account-hub, writing, calendars with sessions, maps, beings. inventory-web gets a minimal redesign only; bench none. Turned down: the order of `apps/README.md`.

### D4. Branch (decided with the maintainer, 2026-11-04)

Work on `docs/web-design`, off current main, merge commits only. Turned down: the session's default branch.

### D5. Chrome of the system: quiet or cards (open)

To be shown side by side on one screen before it is decided.
