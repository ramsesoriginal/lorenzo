import { APP_INFO, type AppRegistry, appsByJob } from './apps';
import { type Autosave, createAutosave } from './autosave';
import { type ConfirmOptions, confirmDialog } from './confirm';
import { closeDialog, fadeOnDismiss, openDialog } from './dialog';
import { createKeymap, GO_KEYS, goChord, type KeyInput } from './keys';
import { type MenuItem, openMenu } from './menu';
import type { PaletteItem } from './palette';
import { mountPalette, type PaletteUi, type PaletteUiOptions } from './palette-ui';
import { clockText, initials, isCurrentPage, navHref } from './pure';
import { changesText, createSaveBar, type SaveBar, type SaveBarHandlers } from './save-bar';
import { readSingleKeys, writeSingleKeys } from './settings';
import { mountShortcuts } from './shortcuts-ui';
import { type PageStateSpec, pageState, type RegionStateSpec, regionState } from './states';
import { bindThemeToggle } from './theme';
import { createToasts, type ToastHandle, type ToastOptions } from './toast';

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
  /**
   * What is only on this device and not yet sent, as paragraphs saying what it is and what happens to
   * it, or null for nothing. Signing out then asks first (ADR 0416).
   */
  unsent?(): string[] | null;
};

export type StatusTone = 'info' | 'error';

/** An action an app puts in the palette. It is the shape of palette-command.schema.json, plus what it does. */
export type PaletteCommand = {
  /** Stable and prefixed by the app: "beings.new". */
  id: string;
  /** Sentence case; an ellipsis when it opens a dialog. */
  name: string;
  icon?: string;
  keys?: string;
  keywords?: string[];
  danger?: boolean;
  run(): void;
};

export type PaletteOptions = {
  commands?: PaletteCommand[];
  /** Entries across apps for a query; the palette has none without it. */
  entries?: PaletteUiOptions['entries'];
  /** How to go to an address; the page's own navigation unless an app (or a test) says otherwise. */
  navigate?(url: string): void;
};

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
  /** Show the navigation links that need `requires` (a `NavItem.requires`): this person may have them. */
  allow(requires: string): void;
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
  /** The palette, Ctrl or Cmd K, and the keys (`?`, G then a letter). Without this call there are none. */
  palette(options?: PaletteOptions): void;
  /** A message at the bottom: a quiet confirmation, or an error that stays and offers `action`. */
  toast(options: ToastOptions): ToastHandle;
  /** A reversible action done: "Moved to the bin", with Undo for ten seconds. */
  undoable(options: { title: string; text?: string; undo(): void }): ToastHandle;
  /** A confirmation for what cannot be undone; true when confirmed. */
  confirm(options: ConfirmOptions): Promise<boolean>;
  /**
   * A state inside a region (loading, empty, failed, partly loaded, in conflict, not on this
   * device), put into `host` in place of what was there; null clears it. The rest of the page keeps
   * working. No state counts what the person cannot see.
   */
  state(host: HTMLElement, spec: RegionStateSpec | null): void;
  /** A state that replaces the whole page, with a mascot: not found, no access, offline, an error. */
  pageState(spec: PageStateSpec): void;
  /**
   * The explicit save bar, for a form whose effects cannot be undone: it opens when the number of
   * changes is above 0, says how many, and offers Discard and Save changes. A failed save keeps the
   * changes and says so. Leaving the page or signing out with changes asks first.
   */
  saveBar(handlers: Omit<SaveBarHandlers, 'onError'>): SaveBar;
  /** The autosave indicator, drawn into `host`: saving, saved, kept on this device, or failed. */
  autosave(host: HTMLElement): Autosave;
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

/** Whether a key was typed into something that takes text, which then keeps it. */
function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof window.HTMLElement)) return false;

  return target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName);
}

function toastsFor(root: HTMLElement) {
  const host = find<HTMLElement>(document, '[data-shell-toasts]');

  return host ? createToasts(host, root.dataset.sprite ?? '') : null;
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
  const toasts = web ? toastsFor(root) : null;
  // The web shell's links are also in the phone's tab bar and the sheet, outside the header.
  const links = [
    ...(web ? document : root).querySelectorAll<HTMLAnchorElement>(
      web ? 'a[data-path]' : 'nav a[data-path]',
    ),
  ];

  const allowed = new Set<string>();
  let library: string | null = null;

  function mark(address: string | null) {
    library = address;
    for (const link of links) {
      const path = link.dataset.path ?? '';
      const href = navHref(
        { href: path, needsLibrary: link.hasAttribute('data-needs-library') },
        address,
      );

      const requires = link.dataset.requires;

      link.hidden = href === null || (requires !== undefined && !allowed.has(requires));
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

  let registry: AppRegistry | null = null;
  let palette: PaletteUi | null = null;
  let hub: string | null = null;
  let shortcutsUi: { open(): void } | null = null;
  const sprite = root.dataset.sprite ?? '';
  const mac = /Mac|iPhone|iPad/.test(navigator.platform);
  const paletteKeys = mac ? '⌘ K' : 'Ctrl K';

  // The list `?` opens; made when first needed, by the palette's keys or the account menu.
  function shortcuts(): { open(): void } {
    shortcutsUi ??= mountShortcuts({
      paletteKeys,
      singleKeys: readSingleKeys,
      setSingleKeys: writeSingleKeys,
      places: () =>
        Object.entries(GO_KEYS).flatMap(([letter, target]) => {
          const name =
            target === 'home'
              ? 'Go to Home'
              : target === 'library'
                ? 'Open the library switcher'
                : target === 'theme'
                  ? 'Change the theme'
                  : APP_INFO[target as keyof typeof APP_INFO]
                    ? `Go to ${APP_INFO[target as keyof typeof APP_INFO].name}`
                    : '';
          const here = target in APP_INFO ? registry?.apps[target]?.url : true;

          return name && here ? [{ chord: `G ${letter.toUpperCase()}`, name }] : [];
        }),
    });

    return shortcutsUi;
  }

  let bar: SaveBar | null = null;
  const unsentNow = (): string[] => {
    const changes = bar?.count() ?? 0;

    return [
      ...(options.unsent?.() ?? []),
      ...(changes > 0 ? [`${changesText(changes)}. Signing out discards them.`] : []),
    ];
  };

  window.addEventListener('beforeunload', (event) => {
    if ((bar?.count() ?? 0) > 0) {
      event.preventDefault();
      event.returnValue = '';
    }
  });

  const accountButton = find<HTMLButtonElement>(root, '[data-shell-account-button]');
  let accountLabel: string | undefined;

  accountButton?.addEventListener('click', () => {
    if (accountButton.getAttribute('aria-expanded') === 'true') return;

    const themeToggle = find<HTMLButtonElement>(root, '[data-theme-toggle]');
    const at = (path: string) => (hub ? new URL(path, hub).href : undefined);
    const hubLink = (label: string, icon: string, path: string): MenuItem[] => {
      const href = at(path);

      return href ? [{ label, icon, href }] : [];
    };
    const items: MenuItem[] = [
      ...hubLink('Profile', 'account', 'profile/'),
      ...hubLink('Notifications', 'notifications', 'notifications/'),
      ...hubLink('Libraries and people', 'library', 'tenants/'),
      ...hubLink('Access tokens and devices', 'token', 'tokens/'),
      { separator: true },
      {
        label: themeToggle?.textContent?.trim() || 'Change theme',
        icon: 'theme-system',
        keys: 'G T',
        run: () => themeToggle?.click(),
      },
      { label: 'Keyboard shortcuts', icon: 'command', keys: '?', run: () => shortcuts().open() },
      { separator: true },
      {
        label: 'Sign out',
        icon: 'logout',
        danger: true,
        run: () => {
          const unsent = unsentNow();

          if (unsent.length === 0) {
            options.onLogout();

            return;
          }
          void confirmDialog({
            title: 'Sign out with unsent changes?',
            body: unsent,
            confirm: 'Sign out anyway',
            cancel: 'Stay signed in',
            danger: true,
          }).then((yes) => {
            if (yes) options.onLogout();
          });
        },
      },
    ];

    openMenu(accountButton, items, {
      label: 'Account',
      sprite,
      ...(accountLabel ? { head: accountLabel } : {}),
    });
  });

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
      if (state.state === 'signed-in') {
        accountLabel = state.label;
        const letters = find<HTMLElement>(root, '[data-shell-initials]');

        if (letters) letters.textContent = initials(state.label);
      }
    },

    accountLink(url) {
      hub = url;
      const link = find<HTMLAnchorElement>(root, '[data-hub]');

      if (!link) return;

      link.href = url;
      link.hidden = false;
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

    allow(requires) {
      allowed.add(requires);
      mark(library);
    },

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

    apps(next) {
      registry = next;
      const host = find<HTMLElement>(document, '[data-shell-apps]');

      if (!host) return;

      host.replaceChildren(
        ...appsByJob(next).map((job) => {
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

    palette(options = {}) {
      if (!web || palette) return;

      const navigate = options.navigate ?? ((url: string) => window.location.assign(url));
      const go = (target: string) => {
        if (target === 'home') navigate('/');
        else if (target === 'theme') find<HTMLButtonElement>(root, '[data-theme-toggle]')?.click();
        else if (target === 'library') {
          const select = find<HTMLSelectElement>(root, '[data-library-select]');

          if (select && !select.closest<HTMLElement>('[data-library-switcher]')?.hidden)
            select.focus();
        } else {
          const url = registry?.apps[target]?.url;

          if (url) navigate(url);
        }
      };

      // The chord a place has, if it has one: no key is no hint.
      const keysOf = (target: string) => {
        const keys = goChord(target);

        return keys ? { keys } : {};
      };

      const items = (): PaletteItem[] => {
        const found: PaletteItem[] = [
          {
            id: 'shell.home',
            group: 'Go to',
            name: 'Home',
            kind: 'This app',
            icon: 'library',
            ...keysOf('home'),
            run: () => go('home'),
          },
          {
            id: 'shell.theme',
            group: 'Actions',
            name: 'Change theme',
            icon: 'theme-system',
            ...keysOf('theme'),
            run: () => go('theme'),
          },
          {
            id: 'shell.shortcuts',
            group: 'Actions',
            name: 'Show keyboard shortcuts',
            icon: 'command',
            keys: '?',
            run: () => shortcuts().open(),
          },
        ];

        if (!find<HTMLElement>(root, '[data-library-switcher]')?.hidden) {
          found.push({
            id: 'shell.library',
            group: 'Actions',
            name: 'Switch library…',
            icon: 'library',
            ...keysOf('library'),
            run: () => go('library'),
          });
        }

        for (const job of registry ? appsByJob(registry) : []) {
          for (const app of job.apps) {
            found.push({
              id: `app:${app.id}`,
              group: 'Go to',
              name: app.name,
              kind: 'Open the app',
              icon: app.icon,
              ...keysOf(app.id),
              preview: { title: app.name, subtitle: 'Open the app', blurb: app.description },
              run: () => go(app.id),
            });
          }
        }

        for (const command of options.commands ?? []) {
          found.push({
            id: command.id,
            group: 'Actions',
            name: command.name,
            ...(command.icon ? { icon: command.icon } : {}),
            ...(command.keys ? { keys: command.keys } : {}),
            ...(command.keywords ? { keywords: command.keywords } : {}),
            ...(command.danger ? { danger: true } : {}),
            run: command.run,
          });
        }

        // An empty hint is no hint.
        return found.map((item) =>
          item.keys === '' ? { ...item, keys: undefined as never } : item,
        );
      };

      palette = mountPalette({
        items,
        sprite,
        recentKey: 'lorenzo:palette-recent',
        ...(options.entries ? { entries: options.entries } : {}),
      });

      const keymap = createKeymap({
        singleKeys: readSingleKeys,
        onGo: go,
        onHelp: () => shortcuts().open(),
        onPalette: () => (palette?.isOpen() ? palette.close() : palette?.open()),
      });

      document.addEventListener('keydown', (event) => {
        if (event.defaultPrevented) return;

        const input: KeyInput = {
          key: event.key,
          ctrlKey: event.ctrlKey,
          metaKey: event.metaKey,
          altKey: event.altKey,
          shiftKey: event.shiftKey,
          typing: isTyping(event.target),
        };

        if (keymap.handle(input)) event.preventDefault();
      });

      for (const opener of document.querySelectorAll<HTMLElement>('[data-shell-open-palette]')) {
        opener.hidden = false;
        opener.addEventListener('click', () => palette?.open());
        const hint = find<HTMLElement>(opener, '[data-shell-palette-keys]');

        if (hint) hint.textContent = paletteKeys;
      }
    },

    toast(toastOptions) {
      return (
        toasts?.show(toastOptions) ?? {
          dismiss() {
            // The old header has no place for messages.
          },
        }
      );
    },

    undoable({ title, text, undo }) {
      return this.toast({
        kind: 'undo',
        title,
        ...(text ? { text } : {}),
        action: { label: 'Undo', run: undo },
      });
    },

    confirm: confirmDialog,

    saveBar(handlers) {
      const host = find<HTMLElement>(document, '[data-shell-savebar]');

      if (!host) return { set() {}, count: () => 0 };

      bar = createSaveBar(host, sprite, {
        ...handlers,
        onError: () => {
          toasts?.show({
            kind: 'error',
            title: 'Couldn’t save',
            text: 'Your changes are still here.',
            action: {
              label: 'Try again',
              run: () => void host.querySelector<HTMLButtonElement>('.btn-primary')?.click(),
            },
          });
        },
      });

      return bar;
    },

    autosave: (host) => createAutosave(host, sprite),

    state(host, spec) {
      host.replaceChildren(...(spec ? [regionState(sprite, spec)] : []));
    },

    pageState(spec) {
      const target = page ?? document.body;

      setHidden(welcome, true);
      setHidden(page, false);
      target.replaceChildren(pageState(sprite.replace(/\/icons\.svg$/, ''), spec));
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
