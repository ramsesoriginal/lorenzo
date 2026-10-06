// The notifications you have sent, grouped by broadcast, with who has read each (RFC 0017 (h): did
// anyone actually read what I sent?). Shown on request.

import { listSentNotifications } from '../../lib/notifications';
import { formatTimestamp } from '../../lib/relativeTime';
import { sayError } from '../../lib/statusLine';
import { cloneRoot, requiredIn } from '../../lib/template';
import type { Notification } from '../../lib/types';

const required = requiredIn('Notifications panel');

// Every row one creation call fanned out shares a batch_id (ADR 0061).
function inBatches(notifications: Notification[]): Notification[][] {
  const batches = new Map<string, Notification[]>();

  for (const notification of notifications) {
    const batch = batches.get(notification.batch_id) ?? [];

    batch.push(notification);
    batches.set(notification.batch_id, batch);
  }

  return [...batches.values()];
}

// `root` is the <NotificationsPanel /> block; `error` is where a failed load is said.
export function bindSent(root: HTMLElement, error: HTMLElement): void {
  const toggle = required<HTMLButtonElement>(root, '[data-sent-toggle]');
  const sent = required<HTMLElement>(root, '[data-sent]');
  const empty = required<HTMLElement>(root, '[data-sent-empty]');
  const list = required<HTMLElement>(root, '[data-sent-list]');

  function renderBatch(recipients: [Notification, ...Notification[]]): HTMLElement {
    const [first] = recipients;
    const row = cloneRoot(root, '[data-batch-template]');
    const readCount = recipients.filter((n) => n.read_at !== null).length;

    required<HTMLElement>(row, '[data-title]').textContent = first.title;
    required<HTMLElement>(row, '[data-meta]').textContent =
      `${first.scope}/${first.type} · ${formatTimestamp(first.created_at)} · ${readCount}/${recipients.length} read`;
    required<HTMLElement>(row, '[data-body]').textContent = first.body;

    // Opens to its text and recipients; the text may be empty, the recipients never are.
    required<HTMLElement>(row, '[data-recipients]').replaceChildren(
      ...recipients.map((recipient) => {
        const item = cloneRoot(root, '[data-recipient-template]');

        item.textContent = recipient.read_at
          ? `${recipient.user_id} · read ${formatTimestamp(recipient.read_at)}`
          : `${recipient.user_id} · unread`;

        return item;
      }),
    );

    return row;
  }

  async function load(): Promise<void> {
    const batches = inBatches((await listSentNotifications()).items);

    list.replaceChildren(
      ...batches.map((batch) => renderBatch(batch as [Notification, ...Notification[]])),
    );
    empty.hidden = batches.length > 0;
  }

  toggle.addEventListener('click', async () => {
    if (!sent.hidden) {
      sent.hidden = true;
      toggle.textContent = "Show notifications I've sent";

      return;
    }

    toggle.disabled = true;

    try {
      await load();
      sent.hidden = false;
      toggle.textContent = 'Hide sent notifications';
    } catch (cause) {
      sayError(error, cause);
    } finally {
      toggle.disabled = false;
    }
  });
}
