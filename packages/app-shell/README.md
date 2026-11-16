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

### The palette and the keys

`shell.palette({ commands, entries, navigate })` ([ADR 0414](../../docs/adr/0414-the-palette-and-the-keyboard-model.md)) mounts one palette and the keys; without the call there are none, and the palette buttons in the header stay hidden.

- **What it lists:** the apps by job from `apps(registry)` ("Go to", with their `G` chords), the shell's own actions (Home, Change theme, Switch library…, Show keyboard shortcuts) and the app's `commands`, which have the shape of [`palette-command.schema.json`](../../apps/brand/palette-command.schema.json) plus a `run`. **Entries across apps** come from the app's `entries(query)`: the shell does not know how to search; a late answer to an older query is ignored. Scopes (Everything, Entries, Apps, Actions) narrow with Tab; the last three opened are remembered in this browser.
- **Keys:** Ctrl or Cmd K opens it (also in a field); `?` lists the shortcuts; `G` then H, S, B, I, C, M, W, O, R, A goes to Home or an app, L focuses the library switcher and T changes the theme. A key typed into a field is the field's. The single keys can be switched off in the `?` list (WCAG 2.1.4); the Ctrl and Cmd ones stay.
- **Pure parts:** `search`, `matchRanges`, `nextScope`, `moveSelection` (`palette.ts`) and `createKeymap` (`keys.ts`) need no page and are tested without one; the dialog is `palette-ui.ts`.

`openDialog`, `closeDialog` and `fadeOnDismiss` (`dialog.ts`) are the one place the dialog closing fade lives: a dialog sets `data-closing`, waits for `animationend`, then closes, and a reopen in the middle wins. The styles are the brand's ([apps/brand](../../apps/brand/README.md#the-web-interface-parts)).

## Tests

`mise run //packages/app-shell:test` covers what needs no page (the first theme, the toggle's wording, a library link's address, the current-page rule, the apps by job, the clock and the tab split) and the web shell: `test/web-shell.test.ts` renders the real `AppPage` with Astro's container API and drives it in a jsdom window, so a markup change that breaks `bindShell` fails here and not in an app. The real-browser checks come with each app's own end-to-end tests when it moves over; the brand's parts have their own in `packages/brand/tests/e2e`.

### Feedback, confirmations and the account menu

([ADR 0415](../../docs/adr/0415-toasts-undo-dialogs-and-menus.md), [ADR 0416](../../docs/adr/0416-first-run-the-account-menu-and-joining.md)) On the web shell:

- `shell.toast({ title, text?, kind?, action? })`: a quiet confirmation that leaves after ten seconds; `kind: 'error'` stays until dismissed and takes `action` ("Try again"). `shell.undoable({ title, text?, undo })` is a toast with Undo. Hovering or focusing a toast pauses it; at most three show, above the status bar (above the tab bar on a phone).
- `shell.confirm({ title, body, confirm, danger?, typeToConfirm? })` resolves true or false. The button says what it does; with `typeToConfirm` it stays off, with the reason beside it, until the name is typed.
- The account button (initials) opens a menu: Profile, Notifications, Libraries and people, Access tokens and devices (from the hub's address), the theme, Keyboard shortcuts, Sign out. Give `bindShell` an `unsent()` that returns paragraphs about what is only on the device and signing out asks first.
- `openMenu(anchor, items, { label, sprite })` is the menu helper (a popover, or a bottom sheet on a phone); `placeMenu` is its pure placement.

### Templates and states

([ADR 0412](../../docs/adr/0412-web-page-templates-and-saving.md), [ADR 0413](../../docs/adr/0413-web-states-and-the-mascots.md), [ADR 0427](../../docs/adr/0427-page-templates-states-and-saving-in-app-shell.md))

- `<AppPage shell="web" template="reading">` gives the page the width of one of the seven templates (`list-detail`, `reading`, `form`, `editor`, `board`, `workspace`, `home`; `pageClass` and `defaultSaving` are the pure parts). Without `template` the page keeps `wrap`.
- `shell.state(host, { kind, noun?, actions? … })` puts a state in a region in place of its rows: `empty`, `empty-search`, `loading` (skeleton lines; `slow` says so), `error` (with a `code` for support), `partial`, `conflict`, `offline`. `shell.state(host, null)` clears it. The words are the design's; an app may give its own `title` and `text`. A state never says how many things the person cannot see.
- `shell.pageState({ art, … })` replaces the page with a mascot: `page-not-found`, `no-access`, `offline-page`, `error-page`, `caught-up` and the empty pages have shared words; an app names its own `art` id and words for the rest. The image is `<brandingUrl>/mascots/ui_<id>.png`; until it is delivered a dashed placeholder with the alt text shows.

### Saving and retry

([ADR 0412](../../docs/adr/0412-web-page-templates-and-saving.md), [ADR 0413](../../docs/adr/0413-web-states-and-the-mascots.md))

- **Explicit save bar** for a form with irreversible effects: `const bar = shell.saveBar({ save, discard })`, then `bar.set(n)` with the number of changes. It opens above the status bar when `n > 0`, says "N changes not saved", and rewrites its buttons only when `n` changes (rewriting them on every edit loses a click on Save). A save that fails keeps the changes and shows an error toast with "Try again". Leaving the page, or signing out, with changes asks first, and the sign-out dialog says how many.
- **Autosave** for writing: `shell.autosave(host).set('saving' | 'saved' | 'device' | 'error')`. `device` says plainly that the change is only on this device and is sent when the connection is back.
- **`retryRead(read, { onRetry })`** runs a read again after a failure, with a wait that doubles from a second to eight, and throws the last error after the last try so the page can show an error state with "Try again". It is for reads only: a write is never retried automatically.

### Links that need something

A `NavItem` may carry `requires: 'signed-in'` (any name the app uses): the link is rendered hidden and stays hidden until `shell.allow('signed-in')` is called, so a page that has nothing for someone is not offered to them (the account hub's navigation). `AppPage`'s `welcome` is optional: without it the page is shown at once, for an app whose pages say their own loading.
