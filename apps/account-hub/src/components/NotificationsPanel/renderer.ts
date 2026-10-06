// /notifications: the inbox, which asks again on an interval, and the sent view (sent.ts).
//
// No server push exists yet (see ADR 0071/RFC 0013) - the interval is a deliberately simple,
// honest "pull", paused while the tab isn't visible so it doesn't poll a backgrounded page forever.

import { onCacheRefreshed } from '../../lib/cache';
import { bindOpensToBody } from '../../lib/disclosure';
import { countUnread } from '../../lib/format';
import { listNotifications, markNotificationRead } from '../../lib/notifications';
import { formatTimestamp } from '../../lib/relativeTime';
import { say, sayError } from '../../lib/statusLine';
import { cloneRoot, requiredIn } from '../../lib/template';
import type { Notification } from '../../lib/types';
import { bindSent } from './sent';

const required = requiredIn('Notifications panel');

const POLL_INTERVAL_MS = 30_000;

// `root` is the <NotificationsPanel /> block. It is shown once; the first load's failure rejects,
// for the page to show. Later ones are said in place.
export async function renderNotificationsPanel(root: HTMLElement): Promise<void> {
  const error = required<HTMLElement>(root, '[data-error]');
  const summary = required<HTMLElement>(root, '[data-summary]');
  const unreadOnly = required<HTMLInputElement>(root, '[data-unread-only]');
  const empty = required<HTMLElement>(root, '[data-empty]');
  const list = required<HTMLElement>(root, '[data-list]');

  function renderNotification(notification: Notification): HTMLElement {
    const row = cloneRoot(root, '[data-notification-template]');
    const markRead = required<HTMLButtonElement>(row, '[data-mark-read]');
    const status = required<HTMLElement>(row, '[data-status]');
    const unread = notification.read_at === null;

    row.classList.add(unread ? 'notification-unread' : 'notification-read');
    required<HTMLElement>(row, '[data-title]').textContent = notification.title;
    required<HTMLElement>(row, '[data-body]').textContent = notification.body;
    required<HTMLElement>(row, '[data-meta]').textContent =
      `${notification.scope}/${notification.type} · ${formatTimestamp(notification.created_at)}`;
    required<HTMLElement>(row, '[data-unread-badge]').hidden = !unread;

    // Opens to its text; one without any has nothing to open to.
    bindOpensToBody(
      required<HTMLElement>(row, '[data-open]'),
      required<HTMLElement>(row, '[data-chevron]'),
      notification.body,
    );

    markRead.hidden = !unread;
    markRead.addEventListener('click', async () => {
      markRead.disabled = true;

      try {
        await markNotificationRead(notification.id);
        await load(true);
      } catch (cause) {
        markRead.disabled = false;
        sayError(status, cause);
      }
    });

    return row;
  }

  // Only the newest load paints: a poll, a refresh and the checkbox can overlap.
  let latest = 0;

  async function load(force = false): Promise<void> {
    const turn = ++latest;
    const page = await listNotifications(unreadOnly.checked, { force });

    if (turn !== latest) return;

    list.replaceChildren(...page.items.map(renderNotification));
    empty.hidden = page.items.length > 0;
    error.hidden = true;
    say(
      summary,
      unreadOnly.checked
        ? `${page.items.length} unread`
        : `${countUnread(page.items)} unread of ${page.items.length} shown`,
    );
  }

  // After the first: a failure is said in place. Asked of the API, not the cache.
  async function reload(): Promise<void> {
    try {
      await load(true);
    } catch (cause) {
      sayError(error, cause);
    }
  }

  required<HTMLElement>(root, '[data-refresh]').addEventListener('click', () => void reload());
  unreadOnly.addEventListener('change', () => void reload());
  bindSent(root, error);

  // What was shown came from the cache, and the API has something different.
  onCacheRefreshed(() => void load().catch(() => {}));

  let pollHandle: ReturnType<typeof setInterval> | undefined;

  function stopPolling(): void {
    clearInterval(pollHandle);
    pollHandle = undefined;
  }

  function startPolling(): void {
    stopPolling();
    pollHandle = setInterval(() => void reload(), POLL_INTERVAL_MS);
  }

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      void reload();
      startPolling();
    } else {
      stopPolling();
    }
  });

  await load();
  root.hidden = false;
  startPolling();
}
