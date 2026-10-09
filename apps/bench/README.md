# apps/bench

Lorenzo Bench, the authoring app ([RFC 0039](../../docs/rfcs/0039-bench-authoring-offline-and-extensibility.md), interface in [RFC 0042](../../docs/rfcs/0042-bench-workbench-interface.md), picture in [docs/design/bench](../../docs/design/bench/README.md), stack in [ADR 0210](../../docs/adr/0210-bench-app-stack-and-workbench-shell.md)).

Today it is the workbench shell (docking tabs, split, float, resize, a palette on Ctrl+K, a layout remembered per device) with Authgear sign-in and a repository picker ([ADR 0211](../../docs/adr/0211-bench-sign-in-and-the-repository-picker.md)). Signed in, it lists the chosen repository's entries and edits an item's name and parents through a command layer ([ADR 0221](../../docs/adr/0221-bench-the-command-layer-and-the-first-editor.md)): every change is a command, shown at once, sent in order, undoable, and compared with the server before it is sent. Without sign-in it runs on a small sample repository in memory. Copy `.env.example` to `.env` to try sign-in locally.

```bash
mise run //apps/bench:dev        # dev server
mise run //apps/bench:test       # unit tests of the layout model (no DOM)
mise run //apps/bench:test-e2e   # Playwright against the built page (set E2E_CHROMIUM to use an installed browser)
```

Keyboard: on a focused tab, Alt+Left/Right reorders, Alt+Shift+arrows splits it to that side, Alt+F floats it.

Layout rules live in `src/workspace/` as pure functions; `src/shell/` is the DOM over them.
