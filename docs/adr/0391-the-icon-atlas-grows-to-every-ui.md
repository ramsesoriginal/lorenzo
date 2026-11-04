# 0391 - The icon atlas grows to every UI

Status: accepted, decided with the maintainer on 2026-11-04. Extends [ADR 0274](0274-the-atlas-grows-for-bench-kinds-and-states.md) and [ADR 0326](0326-moon-phases-in-the-icon-atlas.md); follows [identity §17](../brand/identity.md#17-icon-and-symbol-strategy).

## Context

The atlas, `apps/brand/icons.svg`, held 234 symbols, audited against inventory-web and account-hub ([ADR 0098](0098-branding-css-app-and-package.md)), then against Bench and the planned kinds (ADR 0274) and the moon phases (ADR 0326). Since then more screens have been built or decided, and several of them stand in for an icon with a text character, or with words alone:

- Maps (zoom, whole map, the draw tools, layers, measure, the globe) has text-labelled buttons, and Zoom uses `+` and `−`.
- The LorenzoScript editor's toolbar draws strikethrough, headings and other actions as styled letters.
- Beings' theme toggle uses `☀` and `☾`.
- Repository tooling (publish, retire, update announced, copy, report) is words.
- ADR 0274 left out three icons "because the maintainer did not choose them": a conflict, LIVE, and "only on this device".
- Issue #940 notes that map, scene, session, edition, telling, observance and calendar period have no kind icon, so Bench draws them as the bare entry triangle.

The audit read every app and package with a UI, the design briefs, `v1.0.md`, the RFCs and ADRs, and every issue, pull request and Discussion. It found 72 needs the atlas does not cover, each with Tabler candidates; the maintainer picked from them.

## Decision

- **72 symbols are added**, taken from Tabler Icons outline **3.50.0** (the 234 existing names were all checked against it too). Each follows the existing symbol markup, has a manifest line and a card on `preview/icons.html`:

  | Group | Added (semantic name: Tabler name) |
  | --- | --- |
  | Window chrome: view and theme | `icon-zoom-in` (zoom-in), `icon-zoom-out` (zoom-out), `icon-zoom-fit` (zoom-scan), `icon-center-on` (crosshair), `icon-focus-mode` (focus-2), `icon-theme-light` (sun), `icon-theme-dark` (moon), `icon-theme-system` (sun-moon), `icon-appearance` (typography), `icon-command` (terminal-2) |
  | Editing: the editor toolbar | `icon-heading` (heading), `icon-strikethrough` (strikethrough), `icon-underline` (underline), `icon-subscript` (subscript), `icon-superscript` (superscript), `icon-list-numbered` (list-numbers), `icon-list-check` (list-check), `icon-rule` (separator-horizontal), `icon-entity-link` (brackets-contain), `icon-math` (sum) |
  | Files and media | `icon-export` (file-export), `icon-picture-replace` (photo-up), `icon-unpack` (package-export) |
  | Play | `icon-play` (player-play), `icon-skip` (player-skip-forward) |
  | Visibility and review | `icon-private-off` (lock-open), `icon-redaction` (eye-closed), `icon-eye-check` (eye-check) |
  | Maps | `icon-globe` (globe), `icon-tool-select` (pointer), `icon-tool-circle` (circle-dotted), `icon-tool-line` (line), `icon-tool-area` (polygon), `icon-grid` (grid-dots), `icon-snap` (magnet), `icon-layers` (layers-intersect), `icon-measure` (ruler-measure), `icon-route` (route), `icon-legend` (list-details) |
  | Writing | `icon-word-count` (abacus), `icon-goal` (target-arrow), `icon-cut` (scissors), `icon-join` (arrows-join), `icon-extract` (arrow-bar-right) |
  | Repositories and releases | `icon-discover` (telescope), `icon-publish` (world-upload), `icon-unpublish` (world-off), `icon-announce` (speakerphone), `icon-retired` (archive), `icon-update-available` (package-import), `icon-copy-done` (copy-check), `icon-fork` (git-fork), `icon-merge` (git-merge), `icon-report` (flag-3), `icon-license` (license) |
  | Sync and state (added to Honest state) | `icon-conflict` (git-compare), `icon-live` (broadcast), `icon-local-only` (device-laptop-off), `icon-online` (cloud-check), `icon-storage` (database) |
  | More kinds | `icon-kind-map` (map-2), `icon-kind-scene` (masks-theater), `icon-kind-session` (dice-5), `icon-kind-edition` (versions), `icon-kind-telling` (message-2), `icon-kind-repository` (box-multiple), `icon-kind-period` (calendar-month), `icon-kind-observance` (confetti) |
  | Variants in existing kinds | `icon-kind-being-check` (user-check), `icon-kind-fact-learned` (bulb), `icon-kind-calendar-repeat` (calendar-repeat), `icon-convert` (replace) |

- **Picked as recommended, except five**, which the maintainer chose from the other candidates: `icon-center-on` (crosshair), `icon-command` (terminal-2), `icon-convert` (replace), `icon-discover` (telescope) and `icon-local-only` (device-laptop-off).
- **`icon-extract` draws `arrow-bar-right`**, not the first candidate `file-export`, which `icon-export` already draws: two ideas should not share one drawing outside the alias list.
- **Names follow ADR 0274.** A new kind is `icon-kind-*` (`icon-kind-map`, `-scene`, `-session`, `-edition`, `-telling`, `-repository`, `-period`, `-observance`); a variant of an existing kind keeps its family (`icon-kind-being-check`, `icon-kind-fact-learned`, `icon-kind-calendar-repeat`); the opposite of an icon takes `-off` (`icon-private-off`). The dark theme is `icon-theme-dark` (Tabler's `moon`), named apart from the eight `icon-moon-*` phases.
- **Where the sprite and manifest group them.** The icons for existing groups are appended to them (Window chrome, Editing, Honest state, and the being, fact, clock and calendar kinds); the rest are new groups after Outside Bench (Kinds: more, Files and media, Play, Visibility, Maps, Writing, Repositories), before the custom moon phases.
- **No new aliases.** Eight of the new names could have been aliases of existing icons (`icon-zoom-in` of `icon-add`, `icon-zoom-out` of `icon-decrease`, `icon-entity-link` of `icon-link`, `icon-math` of `icon-formula`, `icon-kind-map` of `icon-map`, `icon-cut` of `icon-split`, `icon-join` of `icon-merge-items`, `icon-kind-edition` of `icon-kind-books`); each gets a symbol of its own.
- **The three icons ADR 0274 left out are now chosen:** `icon-conflict` (git-compare), `icon-live` (broadcast) and `icon-local-only` (device-laptop-off). The words still say the state ([identity §17.8](../brand/identity.md#178-state-and-status)); the icon reinforces them.
- **The existing check applies:** the test in `apps/bench/src/shell/icons.test.ts` fails when the sprite and the manifest list different icons.

## Not added

- Icons for `apps/inventory-mobile` (Material), `apps/inventory-ios` (SF Symbols), the loot-bot's Discord emoji and the CLI's terminal output, which are not part of this atlas.
- Custom drawings. Tabler has no footnote marker, and "who learned what, when" is only loosely a bulb (`icon-kind-fact-learned`); both are possible custom icons under [identity §17.4](../brand/identity.md#174-custom-domain-icons), in the grammar of [ADR 0326](0326-moon-phases-in-the-icon-atlas.md), and are drawn only if wanted.
- A dice and hit-points icon for a game-master companion (Discussions #125 to #138 are ideas, not designs), and an icon for the Overview tab.
- The brand spark in the account-hub header; it is the brand mark, not an interface icon ([§17.1](../brand/identity.md#171-the-lorenzo-spark)).

## Consequences

- The sprite has 306 symbols. It is loaded once and cached, and apps use only the symbols they name; most of the new ones are for screens and kinds that do not draw them yet.
- **No screen changes.** This ADR adds the icons to the atlas only. The text stand-ins it makes replaceable (Maps' zoom and draw tools, the editor toolbar, Beings' theme toggle, repository actions) are follow-up work, and so are the places that stand in for an icon the atlas already has (the stat steppers, `×` and arrow buttons, Sign in and Sign out).
- `icon-theme-dark` and the moon phases are both crescent-like shapes; where both appear, the words name which is which.
