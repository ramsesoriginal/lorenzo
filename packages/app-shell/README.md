# @lorenzo/app-shell

The head, header, footer and page frame of Lorenzo Calendars and Lorenzo Sessions, over the shared brand ([ADR 0322](../../docs/adr/0322-calendars-and-sessions-share-a-header-and-the-brand-base.md)). It ships its source (Astro components and TypeScript) and has no build and no styles of its own: everything is `apps/brand`'s classes and tokens.

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
shell?.status('Log in to open your calendars.');
shell?.reveal(); // hide the welcome and show the page
```

`bindShell` returns null on a page without a header (the auth redirect page). The theme toggle and its attribute handling across Astro's view transitions are done here; the toggle says the theme it switches to ("Dark theme" or "Light theme") and `aria-pressed` says whether dark is on.

## Markup the apps rely on

`[data-site-header]`, `[data-welcome]`, `[data-session]` (the status line, with `[data-session-text]` for its words), and `[data-page]` are this package's own; an app does not draw them. The page links carry `data-path`, and `data-needs-library` marks the ones that need a library.

## Tests

`mise run //packages/app-shell:test` covers what needs no page: the first theme, the toggle's wording, the address of a library's link and the current-page rule. The rest is covered by the end-to-end suites of the apps that use it.
