# @lorenzo/app-shell

The head, header, footer and page frame of the Lorenzo apps that share it, over the shared brand ([ADR 0322](../../docs/adr/0322-calendars-and-sessions-share-a-header-and-the-brand-base.md)). It ships its source (Astro components and TypeScript) and has no build and no styles of its own: everything is `apps/brand`'s classes and tokens.

## Using it

An app's layout is `AppPage.astro`:

```astro
---
import AppPage from '@lorenzo/app-shell/AppPage.astro';
---

<AppPage
  title="Calendars — Lorenzo"
  product="Calendars"
  brandingUrl={BRANDING_CSS_URL}
  themeKey="lorenzo:calendars:theme"
  nav={[{ label: 'Calendars', href: '/' }, { label: 'Events', href: '/events/', needsLibrary: true }]}
  path="apps/calendars"
  welcome={{ title: 'Calendars', text: '…', status: 'Opening your calendars…' }}
>
  <link slot="head" rel="stylesheet" href={appStyles} />
  <slot />
</AppPage>
```

It draws the skip link, the header (the SVG lockup, and the spark alone at 720px and below; the product's name; the page links, collapsing under "Navigation" on a phone; the library switcher; the account; the theme toggle), a welcome section with a status line while the session is checked, the page inside `[data-page]`, and the footer.

The page's script then starts the header:

```ts
import { bindShell } from '@lorenzo/app-shell';

const shell = bindShell({ themeKey, onLogin, onLogout });

shell?.account({ state: 'signed-in', label: viewer.email }); // read aloud by assistive technology, not drawn
shell?.libraries(choices, currentId, (id) => switchTo(id));
shell?.library(tenantAddress); // for the links that belong to a library
shell?.accountLink(hubUrl); // show the link to the account hub, once the app-links registry says where it is
shell?.status('Log in to open your calendars.');
shell?.reveal(); // hide the welcome and show the page
```

`bindShell` returns null on a page without a header (the auth redirect page). The theme toggle and its attribute handling across Astro's view transitions are done here; the toggle says the theme it switches to ("Dark theme" or "Light theme") and `aria-pressed` says whether dark is on.

## Markup the apps rely on

`[data-site-header]`, `[data-welcome]`, `[data-session]` (the status line, with `[data-session-text]` for its words), and `[data-page]` are this package's own; an app does not draw them. The page links carry `data-path`, and `data-needs-library` marks the ones that need a library.

## The web shell (opt-in)

The web interface's shell ([ADR 0426](../../docs/adr/0426-the-web-shell-grows-in-app-shell-opt-in.md), [ADR 0410](../../docs/adr/0410-the-web-shell-header-navigation-and-status-bar.md)) is drawn by the same `AppPage`, when an app asks for it with `shell="web"`. Without the prop an app keeps the one-row header; each app moves over in its own slice and the old header goes when the last one has.

```astro
<AppPage ... shell="web" version="1.2.0" legal={{ notice: '/legal/' }} nav={[{ label: 'Home', href: '/', icon: 'library' }, ...]}>
```

It draws a global bar over an app bar, the state strip, a status bar with the sync state, the app's own meta and the real date and time, the phone's tab bar (the first three links and a More button; the rest go in the sheet), and the sheet that "Apps and about" and "More" open. The same `bindShell` drives it, with four more calls that do nothing in the old header:

```ts
shell?.apps(registry); // the sheet: every deployed app by job (Play, World, Build, You), from GET /app-links
shell?.statusBar({ sync: 'waiting', meta: '12 beings' }); // nothing is claimed until the app says something
shell?.strip({ kind: 'conflict', text: 'Two edits met.', action: { label: 'Review', run } }); // null closes it
shell?.notifications({ count: 3, href: hubUrl + '/notifications/' }); // the bell exists only when an app supplies this
```

`openDialog`, `closeDialog` and `fadeOnDismiss` (`dialog.ts`) are the one place the dialog closing fade lives: a dialog sets `data-closing`, waits for `animationend`, then closes, and a reopen in the middle wins. The styles are the brand's ([apps/brand](../../apps/brand/README.md#the-web-interface-parts)).

## Tests

`mise run //packages/app-shell:test` covers what needs no page (the first theme, the toggle's wording, a library link's address, the current-page rule, the apps by job, the clock and the tab split) and the web shell: `test/web-shell.test.ts` renders the real `AppPage` with Astro's container API and drives it in a jsdom window, so a markup change that breaks `bindShell` fails here and not in an app. The real-browser checks come with each app's own end-to-end tests when it moves over; the brand's parts have their own in `packages/brand/tests/e2e`.
