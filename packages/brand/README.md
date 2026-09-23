# @lorenzo/brand

A thin npm package making [`apps/brand`](../../apps/brand)'s `tokens.css` —
Lorenzo's shared design tokens — `pnpm add`-able by other apps in this
workspace, for bundling at their own build time. See
[ADR 0098](../../docs/adr/0098-branding-css-app-and-package.md).

`tokens.css` in this directory is **generated, not hand-edited** — it's a
copy of `apps/brand/tokens.css`, produced by `mise run //packages/brand:build`.
It's `.gitignore`d, so a clean checkout has none of it; run `build` before
anything tries to consume this package, and `clean` if you want the
generated copy gone from disk again.

Internal, workspace-only for now — not published to a public npm registry
(see ADR 0098's "Not in scope").
