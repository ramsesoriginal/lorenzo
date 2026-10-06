import { showError } from '../../lib/errorUi';
import { markNotificationRead } from '../../lib/notifications';
import { relativeTime } from '../../lib/relativeTime';
import { fromTemplate, requiredIn, rootElement } from '../../lib/template';
import type { Notification } from '../../lib/types';

const required = requiredIn('Briefing');

// The newest unread notifications, each one markable as read from here (which also tells the
// header's count, see markNotificationRead). The section is there only while there are some.
export function showUnread(root: HTMLElement, notifications: Notification[]): void {
  const section = required<HTMLElement>(root, '[data-unread]');
  const list = required<HTMLUListElement>(section, '[data-unread-list]');
  const error = required<HTMLElement>(section, '[data-error]');

  function renderNotification(notification: Notification): HTMLElement {
    const fragment = fromTemplate(root, '[data-notification-template]');
    const item = rootElement(fragment);
    const when = required<HTMLElement>(fragment, '[data-when]');
    const markRead = required<HTMLButtonElement>(fragment, '[data-mark-read]');

    required<HTMLElement>(fragment, '[data-title]').textContent = notification.title;
    required<HTMLElement>(fragment, '[data-body]').textContent = notification.body;
    when.textContent = relativeTime(notification.created_at);
    when.title = new Date(notification.created_at).toLocaleString();

    // Opens to its text; one without any has nothing to open to.
    if (notification.body.trim() === '') {
      required<HTMLElement>(fragment, '[data-chevron]').hidden = true;
      required<HTMLElement>(fragment, '[data-summary]').addEventListener('click', (event) =>
        event.preventDefault(),
      );
    }

    markRead.addEventListener('click', async () => {
      markRead.disabled = true;

      try {
        await markNotificationRead(notification.id);
        error.hidden = true;
        item.remove();
        section.hidden = list.children.length === 0;
      } catch (cause) {
        markRead.disabled = false;
        error.hidden = false;
        showError(error, cause);
      }
    });

    return item;
  }

  list.replaceChildren(...notifications.map(renderNotification));
  section.hidden = notifications.length === 0;
}
