# 0322 - Calendars and Sessions share a header and stand on the brand base

Status: accepted, decided with the maintainer on 2026-10-22. First slice of the Calendars and Sessions polish; later slices are ADR 0323 to 0326.

## Context

`apps/calendars` and `apps/sessions` load all seven brand sheets and then mostly ignore them. Measured against the code on 2026-10-22:

- Neither uses `.card`, `.text-input`, `.field`, `.error-text`, `.status-text`, `.pill`, `.badge`, `.skeleton`, `.spinner` or `.icon`. They use their own `.panel` (calendars 14 times, sessions 9) and `.error`; loading and empty states are plain text.
- Sessions' `.panel` reads `--radius-md` and `--surface-raised`, which no sheet defines, so its panels have square corners and no background.
- Both re-declare `.wrap` (80rem and 70rem, where the brand's is 1120px), `.row`, `.stack` (as a grid, where the brand's is flex), `.caption`, `.editor-toolbar` and `.ls-editor-panes`; calendars also re-declares bare `input`, `select`, `textarea`, `fieldset`, `legend` and the focus ring. `<main class="wrap">` puts `.wrap` on `main`, so the brand's phone rule for `main .wrap` ([ADR 0195](0195-brand-phone-base.md)) does not apply and each app restates the gutters.
- Moon phases are emoji, which ignore the theme and the atlas ([ADR 0274](0274-the-atlas-grows-for-bench-kinds-and-states.md)).
- The header is a lockup, a product label and four buttons. The library picker sits in `<main>`, there is no navigation, and the status of the session check is drawn in the page. The footers and welcome lines are slogans ("Prepare together. Keep the story."), against [identity §14](../brand/identity.md#14-voice-and-writing).
- `Base.astro` is two near-identical 100-line files; the header's account, theme and library-switcher behaviour is also copied between `beings` and `inventory-web`.

[RFC 0036](../rfcs/0036-repository-tooling.md) §2 says the apps do not share a navigation bar or an app switcher. That sentence is about moving between apps, which stay deep links; it does not forbid sharing the code that draws one app's own header.

## Decision

- **A shared header package.** `packages/app-shell` holds the header (lockup, product name, the app's own page links, library switcher, account block, theme toggle) as an Astro component with its behaviour in plain TypeScript, and the page frame (skip link, `<main>` with one `.wrap` inside it, footer). Calendars and Sessions use it in this program. Moving `beings`, `inventory-web` and `account-hub` onto it is a later change of its own. Whether an `.astro` component exports cleanly from a workspace package is checked first; if not, the markup is produced by a TypeScript function and the behaviour stays the same.
- **No app switcher.** Links between apps keep coming from `GET /app-links` ([ADR 0273](0273-app-links-registry.md)); the existing "Account" link stays. The header has an optional notification-bell slot, off in both apps: the bell polls every 60 seconds ([ADR 0265](0265-inventory-web-notification-bell.md)) and neither app has notifications of its own.
- **The library picker is in the header**, an icon and a `.text-input` select shown only when the person has two or more libraries and repositories, as in `beings` and `inventory-web`. Sessions' home lists Sessions across libraries and has no picker; a Session or Scene page names its library.
- **The SVG lockup stays.** The header shows the horizontal lockup in both themes and, at 720px and below, the brand mark alone ([identity §12.2](../brand/identity.md#122-desktop-and-web-app)). A text "✧ Lorenzo" is not used ([§20](../brand/identity.md#20-quick-do--do-not)). `beings` and `inventory-web` keep theirs until they adopt the package.
- **Tokens and brand classes only.** App CSS uses semantic tokens and the brand's classes: `.card` for surfaces (a border, no shadow, [§8.2](../brand/identity.md#82-cards-and-surfaces)), `.text-input` and `.field` for controls, `.error-text` and `.status-text` for messages, `.pill` and `.badge` for tokens, `.skeleton` and `.spinner` for waiting ([§17.9](../brand/identity.md#179-loading)), `.icon` from the atlas for every symbol, the canonical radii, the 8px rhythm, Geist for the interface and Newsreader for titles only, 150 to 220 ms motion that honours reduced motion, one breakpoint at 720px, and 44px targets. Neither app defines `.wrap`, `.row`, `.stack`, `.caption`, `.panel` or its own form-control rules. Gold marks nothing here and visibility stays neutral ([§6.6](../brand/identity.md#66-semantic-color-roles-and-tokens)).
- **Brand additions** go into `apps/brand` when a second app needs them ([ADR 0098](0098-branding-css-app-and-package.md)): `.skip-link` (used by both apps, by no reference app) and `.visually-hidden` (copied inside `inventory-web`'s bell). `.panel` is not added: account-hub already uses that name for something else.
- **Copy** follows §14. The welcome says what the app is and what to do first, in the product's words ("library", "repository", "entry"), with no slogan; the footer names the app and where its source lives, like the reference apps'.
- **Guards.** A unit test reads each of the two apps' CSS and fails on a `var(--x)` that no brand sheet defines (it would have caught `--radius-md`) and on a literal colour, font or shadow outside a short allowlist. The golden-path end-to-end tests also run axe, check that nothing scrolls sideways at 390px, and check that pressed controls are at least 44px. No stylelint: Biome already lints the CSS and a second toolchain is not warranted.

## Not in scope

An app switcher; migrating the other apps' headers; a new theme or token; Bench's own shell; hover previews or a bell in these apps.

## Consequences

- Sessions' panels get a radius and a surface for the first time; calendars and sessions look like one family with `beings` and `inventory-web`.
- The e2e tests depend on roles, labels and text, not on the header's `data-*` attributes (none of the tests use them): the h1 text, the toggle's accessible names ("Dark theme" and "Light theme"), `.brand-mark--light` and `--dark`, and the calendar day classes are kept or changed together with their tests.
- A header change is made once for two apps now and for the others when they adopt the package.
