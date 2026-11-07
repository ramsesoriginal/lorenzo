import { bi } from './doc';
import type { Bi } from './profile';

// What the Lorenzo web apps keep in a browser (ADR 0439), checked on 2026-11-07 in a real browser
// for the keys marked "seen" and from the code for the rest. `files` are the source files that
// touch browser storage; tests/storage-keys.test.ts fails when a file that uses storage is not
// listed here, so a new key cannot ship without the policy being looked at.

export type StorageEntry = {
  key: string;
  store: 'localStorage' | 'sessionStorage' | 'IndexedDB';
  purpose: Bi;
  /** Until when it stays. */
  lasts: Bi;
  /** Source files (relative to the repository root) that read or write it. */
  files: string[];
};

const accountHub = 'apps/account-hub/src';
const readCache = [
  'apps/calendars/src/lib/read-cache.ts',
  'apps/maps/src/lib/read-cache.ts',
  'apps/sessions/src/lib/read-cache.ts',
  'apps/social/src/lib/read-cache.ts',
  'packages/read-cache/src/fetchCache.ts',
];

export const STORAGE_KEYS: StorageEntry[] = [
  {
    key: 'authgear_default_idToken, authgear_default_refreshToken, authgear_default_oidcCodeVerifier',
    store: 'localStorage',
    purpose: bi(
      'Hält Sie angemeldet (Anmelde-Bibliothek von Authgear). Das Identitäts-Token enthält Ihre E-Mail-Adresse.',
      'Keeps you signed in (Authgear sign-in library). The identity token contains your email address.',
    ),
    lasts: bi('Bis zur Abmeldung', 'Until you sign out'),
    files: [],
  },
  {
    key: 'lorenzo:<app>:return, lorenzo.returnTo, lorenzo.invite',
    store: 'sessionStorage',
    purpose: bi(
      'Merkt sich die Seite, auf die Sie nach der Anmeldung zurückkehren, und einen Einladungslink, solange Sie ihn einlösen.',
      'Remembers the page you return to after signing in, and an invite link while you redeem it.',
    ),
    lasts: bi('Bis der Tab geschlossen wird', 'Until the tab is closed'),
    files: [
      `${accountHub}/components/JoinInvite/JoinInvite.astro`,
      `${accountHub}/components/JoinInvite/renderer.ts`,
      `${accountHub}/lib/inviteLink.ts`,
      `${accountHub}/lib/returnPath.ts`,
      'apps/calendars/src/lib/session.ts',
      'apps/calendars/src/pages/auth/redirect.astro',
      'apps/maps/src/lib/sign-in.ts',
      'apps/maps/src/pages/auth/redirect.astro',
      'apps/sessions/src/lib/sign-in.ts',
      'apps/sessions/src/pages/auth/redirect.astro',
      'apps/social/src/lib/sign-in.ts',
      'apps/social/src/pages/auth/redirect.astro',
      'apps/writing/src/lib/writing.ts',
      'apps/writing/src/pages/auth/redirect.astro',
    ],
  },
  {
    key: 'lorenzo.cache.*, lorenzo.<app>.reads.*',
    store: 'sessionStorage',
    purpose: bi(
      'Hält kürzlich gelesene Antworten der Schnittstelle (Ihr Konto, Ihre Bibliotheken), damit Seiten schneller erscheinen.',
      'Holds recently read answers of the API (your account, your libraries) so pages appear faster.',
    ),
    lasts: bi(
      'Bis der Tab geschlossen wird; höchstens 30 Minuten',
      'Until the tab is closed; at most 30 minutes',
    ),
    files: [`${accountHub}/lib/cache.ts`, ...readCache],
  },
  {
    key: 'lorenzo:lastTenant, lorenzo:lastHolder',
    store: 'localStorage',
    purpose: bi(
      'Merkt sich die zuletzt geöffnete Bibliothek und die zuletzt gewählte Figur.',
      'Remembers the library you opened last and the character you chose last.',
    ),
    lasts: bi(
      'Bis zur Abmeldung oder zum Löschen der Browserdaten',
      'Until you sign out or clear browser data',
    ),
    files: [
      'apps/beings/src/lib/lastTenant.ts',
      'apps/beings/src/components/SiteHead/SiteHead.astro',
      'apps/calendars/src/lib/lastTenant.ts',
      'apps/inventory-web/src/lib/lastTenant.ts',
      'apps/inventory-web/src/lib/lastHolder.ts',
      'apps/inventory-web/src/components/SiteHead/SiteHead.astro',
    ],
  },
  {
    key: 'lorenzo:hub-recent',
    store: 'localStorage',
    purpose: bi(
      'Merkt sich die zuletzt geöffneten Seiten des Kontos für „Weitermachen“ auf der Startseite. Bleibt in Ihrem Browser und wird nirgendwohin gesendet.',
      'Remembers the account pages you opened last, for "Continue" on Home. It stays in your browser and is sent nowhere.',
    ),
    lasts: bi('Bis zum Löschen der Browserdaten', 'Until browser data is cleared'),
    files: [`${accountHub}/components/Briefing/renderer.ts`, `${accountHub}/lib/shell.ts`],
  },
  {
    key: 'lorenzo:inventory-web:catalog:*',
    store: 'localStorage',
    purpose: bi(
      'Hält den zuletzt geladenen Katalog einer Bibliothek (Gegenstände mit Namen und Beschreibungen), damit er sofort erscheint.',
      'Holds the catalogue last loaded for a library (items with names and descriptions) so it appears at once.',
    ),
    lasts: bi('Bis zum Löschen der Browserdaten', 'Until browser data is cleared'),
    files: ['apps/inventory-web/src/lib/catalogCache.ts'],
  },
  {
    key: 'lorenzo:<app>:theme, bench:theme, bench:sans, lorenzo:single-keys, lorenzo:maps:look, lorenzo:maps:projection:*',
    store: 'localStorage',
    purpose: bi(
      'Ihre Darstellungswahl (Hell/Dunkel, Schrift, Tastenkürzel, Kartenansicht und Projektion einer Karte).',
      'Your display choices (light/dark, typeface, keyboard shortcuts, map look and the projection of a map).',
    ),
    lasts: bi('Bis zum Löschen der Browserdaten', 'Until browser data is cleared'),
    files: [
      'apps/bench/src/pages/index.astro',
      'apps/bench/src/shell/appearance.ts',
      'apps/maps/src/lib/look.ts',
      'apps/maps/src/lib/sphere-words.ts',
      'packages/app-shell/src/SiteHead.astro',
      'packages/app-shell/src/settings.ts',
      'packages/app-shell/src/theme.ts',
    ],
  },
  {
    key: 'bench:workspace, bench:explorer-order, bench:welcomed, bench:repo:*, lorenzo:palette-recent',
    store: 'localStorage',
    purpose: bi(
      'Anordnung der Fenster in Bench, die Sortierung des Entwurfsbaums, die zuletzt geöffnete Sammlung und die zuletzt genutzten Befehle der Befehlspalette. Bench schreibt die Anordnung auch ohne Anmeldung.',
      'The window layout in Bench, the order of the entry tree, the repository opened last and the commands used last in the command palette. Bench writes the layout even when you are not signed in.',
    ),
    lasts: bi('Bis zum Löschen der Browserdaten', 'Until browser data is cleared'),
    files: [
      'apps/bench/src/shell/repositories.ts',
      'apps/bench/src/shell/session.ts',
      'apps/bench/src/shell/shell.ts',
      'packages/app-shell/src/palette-ui.ts',
    ],
  },
  {
    key: 'lorenzo-writing-drafts',
    store: 'IndexedDB',
    purpose: bi(
      'Ungespeicherte Entwürfe Ihrer Texte in Lorenzo Writing, damit nach einem Absturz nichts verloren geht. Sie enthalten den Text, den Sie schreiben.',
      'Unsaved drafts of your texts in Lorenzo Writing, so nothing is lost after a crash. They contain the text you are writing.',
    ),
    lasts: bi(
      'Bis der Entwurf gespeichert oder verworfen wird',
      'Until the draft is saved or discarded',
    ),
    files: ['apps/writing/src/lib/drafts.ts'],
  },
];
