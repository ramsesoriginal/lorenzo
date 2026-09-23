# Lorenzo — Brand

Lorenzo's whole shared brand layout package, as a plain static site — no
framework, no build step. Include any file here and get Lorenzo's
opinionated, on-brand defaults: colors, fonts, a reset, base element
styling, structural layout, and reusable components. See
[ADR 0098](../../docs/adr/0098-branding-css-app-and-package.md) for why
this exists and how it fits together with
[`packages/brand`](../../packages/brand), and
[docs/brand/identity.md](../../docs/brand/identity.md) for what the values
themselves mean.

## What it does

Six hand-edited stylesheets, in the order any consumer should load them,
plus a self-hosted icon sprite:

1. **`normalize.css`** — a minimal modern reset (box-model, spacing, list/media defaults)
2. **`tokens.css`** — colors (identity.md §6), font-family names, spacing, and radius (§5.2/§8.1/§8.3), as custom properties
3. **`fonts.css`** + **`fonts/`** — the actual self-hosted `@font-face` files backing those font-family names (no CDN — same files `apps/inventory-web`/`apps/account-hub` already use)
4. **`base.css`** — sensible defaults for bare elements: `body`, a corrected `h1`/`h2`/`h3` scale (identity.md §5.3 — H1 may use the display face, H2/H3 never do), links, focus rings, and a subtle background chip on inline `code`
5. **`layout.css`** — the generic page-shell pieces: `.site-header` (with built-in space-between for a right-aligned action), `.wrap` (a centered reading-width container), `.row`/`.row-tight`/`.stack`/`.grid` (the small set of layout primitives — a horizontal row, a tightly-paired icon+label, a vertical stack with consistent gaps, a responsive auto-fit grid), and sensible bare `section`/`footer` rhythm — domain-specific layout stays in each app
6. **`components.css`** — buttons, form controls, tabs, chips, badges, status pills, the neutral visibility-badge treatment, and a generic `.card`/`.card-body` surface, all keyed off `tokens.css`'s semantic roles

`preview/index.html` is built from *only* these — no `<style>` block, no
inline `style=""` anywhere in it except the swatch grid's own color values
(showing what an arbitrary token actually looks like has no substitute for
reading that value directly). That's deliberate: it's the proof that
including this package is enough to style a real page, baseline included,
not just a components catalog.

**`icons.svg`** + **`icons.manifest.yaml`** — a self-hosted SVG sprite of
[Tabler Icons](https://tabler.io/icons) (MIT), referenced via `<use>`
(identity.md §17/§15.6), covering every real icon-worthy action audited
across `apps/inventory-web`/`apps/account-hub` ([issue #178](https://github.com/ramsesoriginal/lorenzo/issues/178)).
Not `<link>`'d like the stylesheets — an SVG sprite isn't a stylesheet, it's
referenced directly wherever an icon is shown. No build step here either:
adding an icon means fetching its real Tabler outline SVG and hand-adding
one `<symbol>` block, same as everything else in this package.

Open `preview/index.html` straight from disk in a browser — there's nothing
to install, run, or build. Edit any file and reload to see the change.

Deploys to Cloudflare Pages via Git integration, same mechanism as
`apps/inventory-web`/`apps/account-hub` (see
[docs/operations/deployment-setup.md](../../docs/operations/deployment-setup.md)).
Once deployed, other apps can point at it at runtime (`PUBLIC_BRANDING_CSS_URL`)
instead of their own bundled copy, for instant cross-app propagation of a
branding change — see ADR 0098 for the tradeoff and why that's opt-in, not
the default.

## Local development

Nothing to install. Just open `preview/index.html` in a browser.

`mise run //apps/brand:lint` format-checks the CSS/HTML with Prettier; the
`dev`/`test`/`build` tasks exist only to satisfy the CI contract every app
under `apps/` shares (see [docs/guides/adding-an-app.md](../../docs/guides/adding-an-app.md)) —
there's no dev server, no automated tests yet, and no build step.
