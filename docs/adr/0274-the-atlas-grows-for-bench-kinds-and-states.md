# 0274 - The icon atlas grows for Bench: one shape per kind, honest states, the views

Status: accepted, decided with the maintainer on 2026-10-12.

Builds on [ADR 0098](0098-branding-css-app-and-package.md) (the brand package and its sprite) and identity §17 (Tabler, semantic names, a manifest, a self-hosted sprite). Bench had its own sixteen icons; this ADR moves it onto the shared atlas and adds what Bench and the planned views need.

## Context

The atlas, `apps/brand/icons.svg`, had 44 icons, audited against inventory-web and account-hub only. Bench drew its own small set in `src/shell/icons.ts` (hand-inlined paths, three kinds of entry: an item, a being, or neither) and used plain text characters (`×`, `↑ ↓ ← →`, `−`, `↳`) as icons in the pack editor, the stats and vocabulary panes and the compare grid. Its title bar used an interface "star" where the brand mark belongs ([identity §17.1](../brand/identity.md#171-the-lorenzo-spark)). The design agreed on a prototype gave every kind of entry its own symbol, and the kinds the product plans (places, facts, clocks, calendars, connections, events, books, chapters) had none.

## Decision

- **One shape per kind**, chosen by the maintainer, each with a family of variants drawn from the same Tabler shape family so a kind stays recognisable when it is added, removed, unknown or in trouble:

  | Kind | Shape | Atlas names |
  | --- | --- | --- |
  | Entry (bare) | triangle | `icon-kind-entity`, `-add`, `-remove`, `-dashed`, `-inverted`, `-off`, `-unknown`, `-info`, `icon-kind-entities` |
  | Item | square | `icon-kind-item` and variants, `icon-kind-items`, `-items-selected` |
  | Being | person | `icon-kind-being` and variants, `icon-kind-beings` |
  | Group | circle | `icon-kind-group` and variants (a group of items, of entries), `icon-kind-groups` |
  | Location | map pin | `icon-kind-location` and variants, `icon-kind-locations` |
  | Fact | hexagon | `icon-kind-fact` and variants, `icon-kind-facts` |
  | Clock | clock | `icon-kind-clock` and variants |
  | Calendar | calendar | `icon-kind-calendar` and variants |
  | Connection | plug | `icon-kind-connection` and variants |
  | Event | timeline event | `icon-kind-event` and variants |
  | Book | book | `icon-kind-book` and variants, `icon-kind-books` |
  | Chapter | text file | `icon-kind-chapter` and variants |

  `icon-kinds` (a triangle, a square and a circle) stands for "the kinds" (the kinds menu).
- **Honest state**, in the manifest's own words: `icon-stale` (out of date), `icon-sync-off`, `icon-reload`, `icon-offline`, `icon-pending` (waiting to sync), `icon-waiting`, `icon-waiting-off`; and the plain `icon-warning`, `icon-error`, `icon-info`, `icon-help` that the kinds' alert, info and unknown variants reuse. Icons reinforce state; the words say it ([identity §17.8](../brand/identity.md#178-state-and-status)).
- **Window chrome, editing, the views, the visibility of notes, and what lies beyond Bench** (tokens, devices, releases, inventory) as proposed in the review the maintainer approved: `icon-float`, `-dock`, `-next`, `-previous`, `-up`, `-down`, `-drag`, `-more`, `-layout-write`/`-inspect`/`-compare`, `-outdent`, `-indent`, `-decrease`, `-inherited-from`; `-redo`, `-sort`, `-filter`, `-pin`, `-tag`, `-stat`, `-formula`, `-picture`, `-picture-main`, `-link`, `-bold`, `-italic`, `-list`, `-quote`, `-code`; `-table`, `-compare`, `-relations`, `-timeline`, `-causality`, `-sheet`, `-manuscript`, `-pack`; `-token`, `-device`, `-release`, `-inventory`, `-account`.
- **Aliases** are listed in the manifest and own no symbol: the audiences of a note reuse existing drawings (`icon-audience-gm` is the lock, `-everyone` the eye, `-some` the group of beings, `-player` the being), `icon-kind-being-add`/`-remove` are the existing assign and unassign icons, and `icon-increase` is the plus.
- **Bench draws from the atlas.** `src/shell/icons.ts` points at the sprite the bundler emits (`@lorenzo/brand/icons.svg`) and names only atlas icons. An entry's icon is the first of its kinds that has one; every planned kind already has its own, so a kind arrives with its icon. `iconButton` makes an icon-only button named by its label. The text stand-ins are icon buttons with names (`Move up`, `Out of its container`, `Decrease by a step`, `Clear the selection`, and so on), and the title bar carries the real brand mark (and Bench gets its favicons).
- **A preview** of the whole atlas, with each icon's source, is `apps/brand/preview/icons.html`.
- **Checks:** a test reads the sprite and the manifest and fails when they list different icons, or when Bench names an icon the sprite lacks.

## Consequences

- The sprite is larger (226 symbols, about 60 KB); it is loaded once and cached, and apps use only the symbols they name. Identity §17.6 asks for a sprite of icons actually used: the manifest and preview say which are used and which are for the kinds and views still to come.
- Two ideas share a drawing in places (an item and a container were both a box before; the atlas now draws an item as a square). Where one drawing serves two names it is an alias, said in the manifest.
- Not added, because the maintainer did not choose them: icons for a conflict, for LIVE, or for "only on this device". The honest-state words carry those until icons are chosen.
- `circle-heart` (not `heart-circle`) is the group's heart; the other 181 names were checked against Tabler 3.49.
