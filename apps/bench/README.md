# apps/bench

Lorenzo Bench, the authoring app ([RFC 0039](../../docs/rfcs/0039-bench-authoring-offline-and-extensibility.md), interface in [RFC 0042](../../docs/rfcs/0042-bench-workbench-interface.md), picture in [docs/design/bench](../../docs/design/bench/README.md), stack in [ADR 0210](../../docs/adr/0210-bench-app-stack-and-workbench-shell.md)).

Today it is the workbench shell on stub data (slice W-A): docking tabs, split, float, resize, a palette (Ctrl+K), and a layout remembered per device. No API, no sign-in, not deployed.

```bash
mise run //apps/bench:dev        # dev server
mise run //apps/bench:test       # unit tests of the layout model (no DOM)
mise run //apps/bench:test-e2e   # Playwright against the built page (set E2E_CHROMIUM to use an installed browser)
```

Keyboard: on a focused tab, Alt+Left/Right reorders, Alt+Shift+arrows splits it to that side, Alt+F floats it.

Layout rules live in `src/workspace/` as pure functions; `src/shell/` is the DOM over them.
