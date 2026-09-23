# @lorenzo/brand

A thin npm package making [`apps/brand`](../../apps/brand) — Lorenzo's
shared brand layout package (tokens, self-hosted fonts, a normalize reset,
base element defaults, structural layout, reusable components, and a
self-hosted Tabler icon sprite) — `pnpm add`-able by other apps in this
workspace, for bundling at their own build time. See
[ADR 0098](../../docs/adr/0098-branding-css-app-and-package.md).

Every file in this directory (`tokens.css`, `fonts.css`, `fonts/`,
`normalize.css`, `base.css`, `layout.css`, `components.css`, `icons.svg`,
`icons.manifest.yaml`) is **generated, not hand-edited** — copies of the
matching files in `apps/brand`, produced by `mise run //packages/brand:build`.
All `.gitignore`d, so a clean checkout has none of them; run `build` before
anything tries to consume this package, and `clean` if you want the
generated copies gone from disk again.

Internal, workspace-only for now — not published to a public npm registry
(see ADR 0098's "Not in scope").
