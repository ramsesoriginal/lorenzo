import { getUnreadCount, NOTIFICATIONS_CHANGED_EVENT } from '../../lib/notifications';
import { required } from './required';

// How often to ask again - the notifications page polls at the same pace (ADR 0085).
const POLL_INTERVAL_MS = 30_000;

// How many notifications are unread, beside the link to them. It's asked again every 30 seconds,
// when the tab comes back, and when this page marks one read - but not while the tab is in the
// background.
export function renderUnreadCount(root: HTMLElement): void {
  const marker = required<HTMLElement>(root, '[data-unread]');
  const link = required<HTMLAnchorElement>(root, 'a[data-path="/notifications/"]');

  let timer: ReturnType<typeof setInterval> | undefined;

  // `force` is false only for the first, which may show what is held; the rest are the poll.
  async function refresh(force = true) {
    let count: number;

    try {
      count = await getUnreadCount({ force });
    } catch {
      // Keeps what it shows; the next ask may do better.
      return;
    }

    marker.hidden = count === 0;
    marker.textContent = count > 99 ? '99+' : String(count);

    if (count === 0) {
      link.removeAttribute('aria-label');
    } else {
      link.setAttribute('aria-label', `Notifications, ${count} unread`);
    }
  }

  function start() {
    stop();
    timer = setInterval(() => void refresh(), POLL_INTERVAL_MS);
  }

  function stop() {
    clearInterval(timer);
    timer = undefined;
  }

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
