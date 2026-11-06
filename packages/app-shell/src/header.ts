import { type AppRegistry, appsByJob } from './apps';
import { closeDialog, fadeOnDismiss, openDialog } from './dialog';
import { clockText, isCurrentPage, navHref } from './pure';
import { bindThemeToggle } from './theme';

export type AccountState =
  | { state: 'checking' }
  | { state: 'signed-out' }
  | { state: 'signed-in'; label?: string }
  | { state: 'error'; message: string };

export type LibraryChoice = { id: string; name: string };

export type ShellOptions = {
  // Where the chosen appearance is kept in this browser.
  themeKey: string;
  onLogin(): void;
  onLogout(): void;
};

export type StatusTone = 'info' | 'error';

/** What the status bar says about the page's data (ADR 0410, D18). */
export type SyncState = 'synced' | 'waiting' | 'offline' | 'conflict';

/** The state strip: shown only when something needs attention, with words, an icon and a pattern. */
export type StripState = {
  kind: 'offline' | 'waiting' | 'conflict';
  text: string;
  action?: { label: string; run(): void };
};

const SYNC_TEXT: Record<SyncState, string> = {
  synced: 'Synced',
  waiting: 'Waiting to sync',
  offline: 'Offline',
  conflict: 'Needs review',
};

const SYNC_ICON: Record<SyncState, string> = {
  synced: 'select-item',
  waiting: 'waiting',
  offline: 'offline',
  conflict: 'conflict',
};

const STRIP_ICON: Record<StripState['kind'], string> = {
  offline: 'offline',
  waiting: 'waiting',
  conflict: 'conflict',
};

/** What an app does to the header and the page frame; the markup is AppPage.astro's. */
export type Shell = {
  account(state: AccountState): void;
  /** The account hub's address, once the registry says where it is. */
  accountLink(url: string): void;
  /**
   * The libraries and repositories the person can use. The switcher is for someone with two or
   * more; with fewer it stays hidden.
   */
  libraries(choices: LibraryChoice[], current: string, onChange: (id: string) => void): void;
  /** The library the page is about, for the navigation links that belong to a library. */
  library(address: string | null): void;
  /** The line under the welcome heading: what is happening, or what went wrong. */
  status(text: string, tone?: StatusTone): void;
  /** Hide the welcome and show the page. */
  reveal(): void;

  // The next four draw only in the web shell (AppPage's `shell="web"`) and do nothing in the old header.

  /** The state strip: a message that needs attention, or null for none (it closes to nothing). */
  strip(state: StripState | null): void;
  /** The status bar: the sync state and the app's own meta (a word count, the carried weight). */
  statusBar(parts: { sync?: SyncState; meta?: string | null }): void;
  /** The apps sheet, from the app registry: every deployed app by job, the current one marked. */
  apps(registry: AppRegistry): void;
  /** The notifications bell, shown only when an app has somewhere to send it. */
  notifications(info: { count: number; href: string } | null): void;
};

function find<T extends HTMLElement>(root: ParentNode, selector: string): T | null {
  return root.querySelector<T>(selector);
}

function setHidden(element: HTMLElement | null, hidden: boolean) {
  if (element) element.hidden = hidden;
}

/** Point a sprite `<use>` at another icon of the same sprite. */
function setIcon(use: Element | null, icon: string) {
  const href = use?.getAttribute('href');

  if (use && href) use.setAttribute('href', `${href.split('#')[0]}#icon-${icon}`);
}

function sameOrigin(url: string): boolean {
  try {
    return new URL(url, window.location.href).origin === window.location.origin;
  } catch {
    return false;
  }
}

/**
 * Starts the header and returns what an app may do to it. Null when this page has no header (the
 * auth redirect page), so a caller can carry on without one.
 */
export function bindShell(options: ShellOptions): Shell | null {
  const root = find<HTMLElement>(document, '[data-site-header]');

  if (!root) return null;

  bindThemeToggle(root, options.themeKey);
  find(root, '[data-login]')?.addEventListener('click', () => options.onLogin());
  find(root, '[data-logout]')?.addEventListener('click', () => options.onLogout());

  const web = root.hasAttribute('data-shell');
  // The web shell's links are also in the phone's tab bar and the sheet, outside the header.
  const links = [
    ...(web ? document : root).querySelectorAll<HTMLAnchorElement>(
      web ? 'a[data-path]' : 'nav a[data-path]',
    ),
  ];

  function mark(address: string | null) {
    for (const link of links) {
      const path = link.dataset.path ?? '';
      const href = navHref(
        { href: path, needsLibrary: link.hasAttribute('data-needs-library') },
        address,
      );

      link.hidden = href === null;
      if (href !== null) link.href = href;

      if (isCurrentPage(path, window.location.pathname)) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    }
  }

  mark(null);

  const checking = find<HTMLElement>(root, '[data-account-checking]');
  const failed = find<HTMLElement>(root, '[data-account-error]');
  const signedOut = find<HTMLElement>(root, '[data-login]');
  const signedIn = find<HTMLElement>(root, '[data-account-signed-in]');
  const label = find<HTMLElement>(root, '[data-account-label]');

  const sheet = find<HTMLDialogElement>(document, '[data-shell-sheet]');

  if (sheet) {
    fadeOnDismiss(sheet);
    for (const opener of document.querySelectorAll('[data-shell-open-sheet]')) {
      opener.addEventListener('click', () => openDialog(sheet));
    }
    sheet.addEventListener('click', (event) => {
      if ((event.target as HTMLElement).closest('a')) closeDialog(sheet);
    });
  }

  const clock = find<HTMLTimeElement>(document, '[data-shell-clock]');

  if (clock) {
    const tick = () => {
      const now = new Date();

      clock.textContent = clockText(now);
      clock.dateTime = now.toISOString();
    };

    tick();
    window.setInterval(tick, 30_000);
  }

  const welcome = find<HTMLElement>(document, '[data-welcome]');
  const page = find<HTMLElement>(document, '[data-page]');
  const statusLine = find<HTMLElement>(document, '[data-session]');
  const statusText = find<HTMLElement>(document, '[data-session-text]');

  return {
    account(state) {
      setHidden(checking, state.state !== 'checking');
      setHidden(failed, state.state !== 'error');
      setHidden(signedOut, state.state !== 'signed-out');
      setHidden(signedIn, state.state !== 'signed-in');

      if (state.state === 'error' && failed) failed.textContent = state.message;
      if (state.state === 'signed-in' && label) {
        label.textContent = state.label ? `Signed in as ${state.label}` : '';
      }
    },

    accountLink(url) {
      const hub = find<HTMLAnchorElement>(root, '[data-hub]');

      if (!hub) return;

      hub.href = url;
      hub.hidden = false;
    },

    libraries(choices, current, onChange) {
      const group = find<HTMLElement>(root, '[data-library-switcher]');
      const select = find<HTMLSelectElement>(root, '[data-library-select]');

      if (!group || !select || choices.length < 2) return;

      select.replaceChildren(
        ...choices.map(
          (choice) => new Option(choice.name, choice.id, false, choice.id === current),
        ),
      );
      select.addEventListener('change', () => onChange(select.value));
      group.hidden = false;
    },

    library: mark,

    status(text, tone = 'info') {
      if (!statusLine) return;

      const spinner = find<HTMLElement>(statusLine, '.spinner');

      setHidden(spinner, true);
      statusLine.hidden = text === '';
      statusLine.classList.toggle('error-text', tone === 'error');
      statusLine.classList.toggle('status-text', tone !== 'error');
      statusLine.setAttribute('role', tone === 'error' ? 'alert' : 'status');
      (statusText ?? statusLine).textContent = text;
    },

    reveal() {
      setHidden(welcome, true);
      setHidden(page, false);
    },

    strip(state) {
      const strip = find<HTMLElement>(root, '[data-shell-strip]');
      const inner = find<HTMLElement>(root, '.shell-strip-in');

      if (!strip || !inner) return;

      if (state) {
        inner.dataset.kind = state.kind;
        setIcon(find(inner, '[data-shell-strip-icon]'), STRIP_ICON[state.kind]);
        const text = find<HTMLElement>(inner, '[data-shell-strip-text]');
        if (text) text.textContent = state.text;

        const action = find<HTMLButtonElement>(inner, '[data-shell-strip-action]');
        if (action) {
          action.hidden = !state.action;
          action.textContent = state.action?.label ?? '';
          action.onclick = state.action ? () => state.action?.run() : null;
        }
      }

      if (state) strip.setAttribute('data-open', '');
      else strip.removeAttribute('data-open');
    },

    statusBar(parts) {
      if (parts.sync) {
        const sync = find<HTMLElement>(document, '[data-shell-sync]');

        if (sync) {
          sync.hidden = false;
          sync.dataset.kind = parts.sync;
          setIcon(find(sync, '[data-shell-sync-icon]'), SYNC_ICON[parts.sync]);
          const text = find<HTMLElement>(sync, '[data-shell-sync-text]');
          if (text) text.textContent = SYNC_TEXT[parts.sync];
        }
      }

      if (parts.meta !== undefined) {
        const meta = find<HTMLElement>(document, '[data-shell-meta]');

        if (meta) {
          meta.textContent = parts.meta ?? '';
          meta.hidden = !parts.meta;
        }
      }
    },

    apps(registry) {
      const host = find<HTMLElement>(document, '[data-shell-apps]');

      if (!host) return;

      host.replaceChildren(
        ...appsByJob(registry).map((job) => {
          const column = document.createElement('div');
          const label = document.createElement('div');

          label.className = 'menu-label';
          label.textContent = job.label;
          column.append(
            label,
            ...job.apps.map((app) => {
              const link = document.createElement('a');

              link.className = 'l';
              link.href = app.url;
              link.dataset.app = app.id;
              link.title = app.description;
              if (sameOrigin(app.url)) link.setAttribute('aria-current', 'page');
              link.textContent = app.name;

              return link;
            }),
          );

          return column;
        }),
      );
    },

    notifications(info) {
      const bell = find<HTMLAnchorElement>(root, '[data-shell-bell]');

      if (!bell) return;

      bell.hidden = info === null;
      if (!info) return;

      bell.href = info.href;
      bell.setAttribute(
        'aria-label',
        info.count > 0 ? `Notifications, ${info.count} unread` : 'Notifications',
      );
      const count = find<HTMLElement>(bell, '[data-shell-bell-count]');
      if (count) count.textContent = info.count > 0 ? String(info.count) : '';
    },
  };
}
