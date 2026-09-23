# Lorenzo — Brand Tokens

Lorenzo's shared design tokens (`tokens.css`) as a plain static site — no
framework, no build step. See [ADR 0098](../../docs/adr/0098-branding-css-app-and-package.md)
for why this exists and how it fits together with
[`packages/brand`](../../packages/brand), and
[docs/brand/identity.md](../../docs/brand/identity.md) §5.2/§6/§8.1/§8.3 for
what the values themselves mean.

## What it does

`tokens.css` is the single hand-edited source of these design tokens —
colors, font-family names, spacing, and radius. `preview/index.html`
`<link>`s to it directly and renders a live sample (surfaces, buttons,
status pills, visibility badges, a type sample), with a light/dark toggle.

Open `preview/index.html` straight from disk in a browser — there's nothing
to install, run, or build. Edit `tokens.css` and reload to see the change.

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
