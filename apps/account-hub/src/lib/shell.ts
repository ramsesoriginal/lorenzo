// The hub's frame (UI-D, ADR 0410, ADR 0416): the web shell's header, status bar and menus, started
// on every page. It is what the old site header did - who is signed in, which pages this person has,
// the unread count - handed to @lorenzo/app-shell.

import { getAppLinks } from '@lorenzo/api-client';
import { bindShell, type Shell } from '@lorenzo/app-shell';
import { getUserInfo, isAuthConfigured, isAuthenticated, login, logout } from './auth';
import { API_BASE_URL, RECENT_KEY, THEME_KEY } from './config';
import { showsDiscover } from './discover';
import { getFacets } from './discoverApi';
import { isTenantAdmin } from './format';
import { pageTitle, parseRecent, rememberPage } from './home';
import { getMe } from './me';
import { getUnreadCount, NOTIFICATIONS_CHANGED_EVENT } from './notifications';
import { bindPrefetch } from './prefetch';
import { sayError } from './statusLine';
import { canCreateTenants, isRepository } from './tenantKind';
import { listMyTenants } from './tenants';

// How often to ask again - the notifications page polls at the same pace (ADR 0085).
const POLL_INTERVAL_MS = 30_000;

/**
 * Which pages this person has: whoever is signed in gets the ones that need only that, and the rest
 * as `GET /me`, `GET /tenants` and the discover facets say - the same rules the pages themselves
 * apply. An answer that does not come leaves its links hidden, rather than showing one that may lead
 * nowhere.
 */
export async function allowedPages(): Promise<string[]> {
  const allowed = ['signed-in'];
  const [me, tenants, facets] = await Promise.allSettled([getMe(), listMyTenants(), getFacets()]);

  // ADR 0175: who may create a library or a repository.
  const mayCreate = me.status === 'fulfilled' && canCreateTenants(me.value);

  if (mayCreate) allowed.push('create-tenant');

  // /beings lists the beings of a repository, or of a library where you GM a campaign.
  const gms = me.status === 'fulfilled' && me.value.campaign_gm_grants.length > 0;
  const inRepository = tenants.status === 'fulfilled' && tenants.value.items.some(isRepository);

  if (gms || inRepository) allowed.push('beings');

  // Shelf is where a library's owners and organizers see the repositories it may copy from.
  if (
    tenants.status === 'fulfilled' &&
    tenants.value.items.some((tenant) => !isRepository(tenant) && isTenantAdmin(tenant))
  ) {
    allowed.push('library-admin');
  }

  // Studio is where a repository is run: for anyone who works on one, and for an account that may
  // make one (ADR 0175).
  if (inRepository || mayCreate) allowed.push('repository-work');

  // Discover is where public repositories are found, for a deployment that accepts them (ADR 0290,
  // ADR 0292): the facets say so, and where they do not come there is no link.
  if (facets.status === 'fulfilled' && showsDiscover(facets.value)) allowed.push('discover');

  return allowed;
}

/** The unread count on the bell: asked again every 30 seconds, when the tab comes back, and when a notification is marked read. */
function watchUnread(shell: Shell): void {
  let timer: ReturnType<typeof setInterval> | undefined;

  // `force` is false only for the first, which may show what is held; the rest are the poll.
  async function refresh(force = true) {
    try {
      shell.notifications({ count: await getUnreadCount({ force }), href: '/notifications/' });
    } catch {
      // Keeps what it shows; the next ask may do better.
    }
  }

  const stop = () => {
    clearInterval(timer);
    timer = undefined;
  };
  const start = () => {
    stop();
    timer = setInterval(() => void refresh(), POLL_INTERVAL_MS);
  };

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      void refresh();
      start();
    } else {
      stop();
    }
  });
  window.addEventListener(NOTIFICATIONS_CHANGED_EVENT, () => void refresh());
  void refresh(false);
  if (document.visibilityState === 'visible') start();
}

// The registry is public and needs no Referer: a page whose address holds a live link or code (/join,
// /device, ADR 0171) must not send one with anything it asks of the API.
const withoutReferrer: typeof fetch = (input, init) =>
  fetch(input, { ...init, referrerPolicy: 'no-referrer' });

// Pages whose address is a secret or only a step are not remembered for Continue.
const NOT_REMEMBERED = ['/', '/device/', '/join/'];

function rememberThisPage(): void {
  const path = window.location.pathname;

  if (NOT_REMEMBERED.includes(path) || path.startsWith('/auth/')) return;

  try {
    const recent = parseRecent(window.localStorage.getItem(RECENT_KEY));

    window.localStorage.setItem(
      RECENT_KEY,
      JSON.stringify(rememberPage(recent, { href: path, title: pageTitle(document.title) })),
    );
  } catch {
    // Private browsing: Continue simply remembers nothing.
  }
}

let started: Shell | null = null;

/** The shell this page started, for a page that gives feedback (a toast, an Undo); null before it starts. */
export function currentShell(): Shell | null {
  return started;
}

/** Starts the frame. The page's own script does the page; this does who is signed in and where to go. */
export async function startShell(): Promise<void> {
  const shell = bindShell({
    themeKey: THEME_KEY,
    onLogin: () => void login(),
    onLogout: () => void logout(),
  });

  if (!shell) return;

  started = shell;
  // The hub is where the account menu's pages are.
  shell.accountLink(`${window.location.origin}/`);
  shell.palette();
  void getAppLinks(API_BASE_URL, withoutReferrer)
    .then((registry) => shell.apps(registry))
    .catch(() => {});

  // The auth redirect page is still finishing the login, so it shows neither state.
  if (window.location.pathname.startsWith('/auth/')) return;

  shell.account({ state: 'checking' });

  if (!isAuthConfigured()) {
    shell.account({ state: 'error', message: 'Sign-in is not set up for this app yet.' });

    return;
  }

  try {
    if (!(await isAuthenticated())) {
      shell.account({ state: 'signed-out' });

      return;
    }

    const info = await getUserInfo();

    shell.account({ state: 'signed-in', label: info.email ?? info.sub });
  } catch (cause) {
    const line = document.createElement('span');

    sayError(line, cause);
    shell.account({ state: 'error', message: line.textContent ?? 'Could not check your session.' });

    return;
  }

  rememberThisPage();
  // Just a convenience - on failure, the header stays without it.
  watchUnread(shell);
  bindPrefetch();
  try {
    for (const page of await allowedPages()) shell.allow(page);
  } catch {
    // Without an answer the links stay hidden.
  }
}
