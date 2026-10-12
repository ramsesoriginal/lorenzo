import { notificationsUrl } from '../../lib/appLinks';
import { ACCOUNT_HUB_URL } from '../../lib/config';
import { errorMessage } from '../../lib/errorMessage';
import {
  badgeText,
  bellLabel,
  hubNotificationsUrl,
  notificationLink,
  pollDelay,
} from '../../lib/notificationBell';
import { loadRecent, markAllRead, markRead } from '../../lib/notifications';
import { relativeTime } from '../../lib/relativeTime';
import { requiredIn } from '../../lib/template';

const required = requiredIn('Site header');

type Recent = Awaited<ReturnType<typeof loadRecent>>;

const FOCUSABLE = 'a[href], button:not([disabled])';

// The bell beside who is signed in: how many are unread, and a dropdown of the latest with a
// way to read them off (ADR 0265). It asks on load, on coming back to the tab, when it opens,
// and every minute while the tab is visible; failing, it keeps what it showed and backs off.
// Only called for someone signed in, so a signed-out page never asks.
export function renderNotificationBell(root: HTMLElement): void {
  const bell = required<HTMLElement>(root, '[data-bell]');
  const button = required<HTMLButtonElement>(bell, '[data-bell-button]');
  const badge = required<HTMLElement>(bell, '[data-bell-badge]');
  const announce = required<HTMLElement>(bell, '[data-bell-announce]');
  const panel = required<HTMLElement>(bell, '[data-bell-panel]');
  const list = required<HTMLElement>(bell, '[data-bell-list]');
  const message = required<HTMLElement>(bell, '[data-bell-message]');
  const markAll = required<HTMLButtonElement>(bell, '[data-bell-mark-all]');
  const seeAll = required<HTMLAnchorElement>(bell, '[data-bell-all]');

  // The registry knows where the hub is; the build's own address is the answer until it replies.
  seeAll.href = hubNotificationsUrl(ACCOUNT_HUB_URL);
  void notificationsUrl(ACCOUNT_HUB_URL).then((url) => {
    seeAll.href = url;
  });

  let shown: Recent | undefined;
  let failures = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  // Only the newest answer paints: a poll and a click can overlap.
  let latest = 0;

  function say(text: string) {
    message.textContent = text;
    message.hidden = !text;
  }

  function paint(recent: Recent) {
    const previous = shown?.unread;

    shown = recent;
    badge.textContent = badgeText(recent.unread);
    badge.hidden = recent.unread === 0;
    button.setAttribute('aria-label', bellLabel(recent.unread));
    markAll.hidden = recent.unread === 0;

    // A new one is said once; the first count and every drop are not news.
    if (previous !== undefined && recent.unread > previous) {
      announce.textContent = `${recent.unread - previous} new, ${recent.unread} unread`;
    }

    list.replaceChildren(...recent.items.map(renderItem));
    say(recent.items.length === 0 ? 'No notifications yet.' : '');
  }

  function renderItem(n: Recent['items'][number]): HTMLElement {
    const unread = n.read_at === null;
    const item = document.createElement('li');
    const main = document.createElement('div');
    const href = notificationLink(n);
    const title = document.createElement(href ? 'a' : 'span');

    item.className = `bell-item${unread ? ' bell-item--unread' : ''}`;
    main.className = 'bell-item-main';
    title.className = 'bell-item-title';
    title.textContent = n.title;
    if (title instanceof HTMLAnchorElement && href) title.href = href;
    main.append(title);

    if (n.body) {
      const body = document.createElement('p');

      body.className = 'bell-item-body';
      body.textContent = n.body;
      main.append(body);
    }

    const time = document.createElement('p');

    time.className = 'bell-item-time';
    time.textContent = relativeTime(n.created_at);
    main.append(time);
    item.append(main);

    if (unread) {
      const read = document.createElement('button');

      read.type = 'button';
      read.className = 'btn btn-secondary';
      read.textContent = 'Mark read';
      read.setAttribute('aria-label', `Mark read: ${n.title}`);
      read.addEventListener('click', async () => {
        read.disabled = true;

        try {
          await markRead(n.id);
          await refresh();
        } catch (cause) {
          read.disabled = false;
          say(`Could not mark it read: ${errorMessage(cause)}`);
        }
      });
      item.append(read);
    }

    return item;
  }

  async function refresh(): Promise<void> {
    const turn = ++latest;

    try {
      const recent = await loadRecent();

      if (turn !== latest) return;

      failures = 0;
      paint(recent);
    } catch {
      if (turn !== latest) return;

      failures += 1;

      // The bell keeps working: what was shown stays, or the dropdown says why it is empty.
      if (!shown) {
        list.replaceChildren();
        say('Could not load notifications.');
      }
    }
  }

  function schedule() {
    clearTimeout(timer);
    timer = undefined;

    const delay = pollDelay(document.visibilityState === 'visible', failures);

    if (delay === null) return;

    timer = setTimeout(async () => {
      await refresh();
      schedule();
    }, delay);
  }

  function focusables(): HTMLElement[] {
    return [button, ...panel.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((e) => !e.hidden);
  }

  function open() {
    button.setAttribute('aria-expanded', 'true');
    panel.hidden = false;
    void refresh();
    panel.querySelector<HTMLElement>(FOCUSABLE)?.focus();
  }

  function close(returnFocus = true) {
    if (panel.hidden) return;

    button.setAttribute('aria-expanded', 'false');
    panel.hidden = true;
    if (returnFocus) button.focus();
  }

  button.addEventListener('click', () => (panel.hidden ? open() : close()));

  markAll.addEventListener('click', async () => {
    markAll.disabled = true;

    try {
      const { failed } = await markAllRead();

      await refresh();
      if (failed > 0) say(`Could not mark ${failed} as read.`);
    } catch (cause) {
      say(`Could not mark them read: ${errorMessage(cause)}`);
    } finally {
      markAll.disabled = false;
    }
  });

  // Escape closes wherever the focus has got to (a button that was clicked may be gone).
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !panel.hidden) {
      event.preventDefault();
      close();
    }
  });

  // Tab stays between the bell and the end of its dropdown.
  bell.addEventListener('keydown', (event) => {
    if (panel.hidden || event.key !== 'Tab') return;

    const stops = focusables();
    const first = stops[0];
    const last = stops[stops.length - 1];

    if (!first || !last) return;

    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });

  document.addEventListener('pointerdown', (event) => {
    if (event.target instanceof Node && !bell.contains(event.target)) close(false);
  });

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') void refresh().then(schedule);
    else schedule();
  });

  void refresh().then(schedule);
}
