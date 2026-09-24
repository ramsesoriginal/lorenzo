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

Seven hand-edited stylesheets, in the order any consumer should load them,
plus a self-hosted icon sprite:

1. **`normalize.css`** — a minimal modern reset (box-model, spacing, list/media defaults)
2. **`tokens.css`** — colors (identity.md §6), font-family names, spacing, and radius (§5.2/§8.1/§8.3), as custom properties
3. **`fonts.css`** + **`fonts/`** — the actual self-hosted `@font-face` files backing those font-family names (no CDN — same files `apps/inventory-web`/`apps/account-hub` already use)
4. **`base.css`** — sensible defaults for bare elements: `body`, a corrected `h1`/`h2`/`h3` scale (identity.md §5.3 — H1 may use the display face, H2/H3 never do), links, focus rings, a subtle background chip on inline `code`, and `scrollbar-gutter: stable` everywhere so content never shifts width when a page grows past one screen
5. **`layout.css`** — the generic page-shell pieces: `.site-header` (with built-in space-between for a right-aligned action), `.wrap` (a centered reading-width container), `.with-sidebar`/`.sidebar` (a narrow nav rail beside a wider content column, stacking to one column below 720px), `.row`/`.row-tight`/`.stack`/`.grid` (the small set of layout primitives — a horizontal row, a tightly-paired icon+label, a vertical stack with consistent gaps, a responsive auto-fit grid), and sensible bare `section`/`footer` rhythm — domain-specific layout stays in each app
6. **`components.css`** — buttons, form controls (including `textarea`/`select`/checkbox/radio/range/a custom `.switch` toggle), tabs, chips, badges, status pills, the neutral visibility-badge treatment, a generic `.card`/`.card-body` surface, native `dialog`/`dialog::backdrop` styling, a `.tree` (nested `<details>`/`<summary>`) disclosure pattern, `.editor-toolbar`/`.editor-content` for a custom rich-text-style editor, and the LorenzoScript editor's panes (`.ls-editor`) and rendered text (`.ls-content`, ADR 0106), all keyed off `tokens.css`'s semantic roles
7. **`motion.css`** — every animation pattern the brand actually uses (identity.md §11): routine `.spinner`/`.skeleton`/`.progress-bar`, the rare branded `.spark-loader`, `.glow-canonical` (Gold's one job, as a literal conic-gradient halo), and a set of opt-in editorial effects (`.typewriter`, `.stat-count` count-up, `.reading-progress` scroll-linked bar, `.stagger` sibling fade-in, `.squircle` corners) — every experimental technique (`corner-shape`, `sibling-index()`, `animation-timeline: scroll()`) is wrapped in `@supports` with a plain, static fallback, and a global `prefers-reduced-motion: reduce` override caps everything else

`preview/index.html` is built from *only* the first six — no `<style>`
block, no inline `style=""` anywhere in it except the swatch grid's own
color values (showing what an arbitrary token actually looks like has no
substitute for reading that value directly). That's deliberate: it's the
proof that including this package is enough to style a real page, baseline
included, not just a components catalog.

Six further preview pages exercise everything else: `preview/motion.html`
(every `motion.css` technique, live), `preview/dialogs.html` (a single
modal `<dialog>`, and two non-modal, semi-overlapping dialogs open at
once), `preview/forms.html` (every field type on one form), `preview/trees.html`
(a nested world hierarchy), `preview/editors.html` (`.editor-toolbar` +
`.editor-content` composed with `.card`), and `preview/content/` — seven
"thematic lorem ipsum" pages (a 1993 tax office, a university research
project, a starship crew, a Renaissance merchant family, a cyberpunk
corporation, a mundane apartment inventory, a traditional fantasy
campaign), each a full mini-page built from nothing but this package's own
classes, proving the style reads well across completely unrelated content,
not just Lorenzo's own domain.

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
