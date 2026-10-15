# apps/bench

Lorenzo Bench, the authoring app ([RFC 0039](../../docs/rfcs/0039-bench-authoring-offline-and-extensibility.md), interface in [RFC 0042](../../docs/rfcs/0042-bench-workbench-interface.md), picture in [docs/design/bench](../../docs/design/bench/README.md), stack in [ADR 0210](../../docs/adr/0210-bench-app-stack-and-workbench-shell.md)).

## What is built

The workbench has docking tabs, splits, floating panes, resizing, a Ctrl+K palette, and layouts remembered per device. Authgear sign-in opens a repository picker ([ADR 0211](../../docs/adr/0211-bench-sign-in-and-the-repository-picker.md)); without sign-in it uses a small sample repository in memory.

Signed in, an explorer shows the repository as a searchable tree with kinds and ordered parents. Entries can be created, renamed and moved, with descriptions and notes edited where they are drawn in LorenzoScript. Links use an entry picker and previews; text can contain pictures and stat chips. Changes go through the command layer: shown at once, sent in order, compared with the server before sending, and undoable ([ADR 0221](../../docs/adr/0221-bench-the-command-layer-and-the-first-editor.md) onward).

The editor also has stats and tags, formulas and the stat vocabulary, main and inherited pictures, a structured pack editor, ancestry, a Table pane and comparison grid. Write, Inspect and Compare presets arrange the panes; the status bar and conflict dialog show unsent changes and conflicts. The repository menu, first-run welcome, appearance controls and shared kind icons are built (ADR 0247 to 0275).

**Persistent offline editing is not built yet.** Commands and unsent changes are held in memory; per-user IndexedDB, a shell service worker, persistent outbox, offline pinning and stored-base conflict review remain slices B4/B5 of RFC 0039. Prototype map, timeline, calendar, manuscript and template views are design references, not implemented editors.

## Run and check

Copy `.env.example` to `.env` to try sign-in locally.

```bash
mise run //apps/bench:dev        # dev server
mise run //apps/bench:lint       # Biome, Astro and Prettier checks
mise run //apps/bench:test       # unit tests of workspace, commands and editor logic
mise run //apps/bench:test-e2e   # Playwright; E2E_CHROMIUM selects an installed browser
mise run //apps/bench:build      # static site in dist/
```

Keyboard: on a focused tab, Alt+Left/Right reorders, Alt+Shift+arrows splits it to that side, Alt+F floats it, Ctrl+Alt+arrows move it into the group beside, Alt+D docks it back; the palette lists them ([ADR 0257](../../docs/adr/0257-bench-keyboard-moves-for-tabs.md)).

Layout rules live in `src/workspace/` as pure functions; `src/shell/` is the DOM over them.
