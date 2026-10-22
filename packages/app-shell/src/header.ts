import { isCurrentPage, navHref } from './pure';
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
};

function find<T extends HTMLElement>(root: ParentNode, selector: string): T | null {
  return root.querySelector<T>(selector);
}

function setHidden(element: HTMLElement | null, hidden: boolean) {
  if (element) element.hidden = hidden;
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

  const links = [...root.querySelectorAll<HTMLAnchorElement>('nav a[data-path]')];

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
  };
}
