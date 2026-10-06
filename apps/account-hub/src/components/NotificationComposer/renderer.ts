// Notification composer, shared by tenant-scope and campaign-scope sending (RFC 0017 (g)). The
// ADR 0074 picker is an *optional* recipient resolver here - leaving it empty broadcasts to the
// scope's whole roster, matching NotificationCreate's own documented behavior rather than
// requiring a recipient. Character-scope and group-scope sending are deliberately not offered -
// this app has no character/group management surface for a GM to pick a sensible target from yet.

import { displayNameFor } from '../../lib/format';
import { say, sayError } from '../../lib/statusLine';
import { fromTemplate, requiredIn } from '../../lib/template';
import type { Notification, NotificationCreate, UserRefOut } from '../../lib/types';
import { renderUserPicker } from '../UserPicker/renderer';

const required = requiredIn('Notification composer');

// The Send button sits outside the <form> (see the markup), so they are tied by an id.
let composers = 0;

// `root` is the <NotificationComposer /> block.
export function renderNotificationComposer(
  root: HTMLElement,
  send: (body: NotificationCreate) => Promise<Notification[]>,
): void {
  const form = required<HTMLFormElement>(root, '[data-form]');
  const typeInput = required<HTMLInputElement>(root, '[data-type]');
  const titleInput = required<HTMLInputElement>(root, '[data-title]');
  const bodyInput = required<HTMLTextAreaElement>(root, '[data-body]');
  const broadcasting = required<HTMLElement>(root, '[data-broadcasting]');
  const picking = required<HTMLElement>(root, '[data-picking]');
  const chosen = required<HTMLElement>(root, '[data-chosen]');
  const sendButton = required<HTMLButtonElement>(root, '[data-send]');
  const status = required<HTMLElement>(root, '[data-status]');

  composers += 1;
  form.id = `notification-composer-${composers}`;
  sendButton.setAttribute('form', form.id);

  let recipient: UserRefOut | null = null;

  function showBroadcastState() {
    recipient = null;
    picking.replaceChildren();
    picking.hidden = true;
    chosen.hidden = true;
    broadcasting.hidden = false;
  }

  function showRecipientState(user: UserRefOut) {
    required<HTMLElement>(chosen, '[data-chosen-text]').textContent =
      `Sending to: ${displayNameFor({ ...user, user_id: user.id })}`;
    broadcasting.hidden = true;
    picking.hidden = true;
    chosen.hidden = false;
  }

  // A fresh picker each time, so a lookup left half done is not there when it is asked for again.
  required<HTMLButtonElement>(broadcasting, '[data-pick]').addEventListener('click', () => {
    picking.replaceChildren(fromTemplate(root, '[data-picker-template]'));
    renderUserPicker(required<HTMLElement>(picking, '[data-user-picker]'), (user) => {
      recipient = user;
      showRecipientState(user);
    });
    broadcasting.hidden = true;
    picking.hidden = false;
  });

  required<HTMLButtonElement>(chosen, '[data-clear]').addEventListener('click', showBroadcastState);

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    say(status, 'Sending…');
    try {
      const sent = await send({
        recipient_user_id: recipient?.id ?? null,
        type: typeInput.value.trim(),
        title: titleInput.value.trim(),
        body: bodyInput.value.trim(),
      });
      say(status, `Sent to ${sent.length} recipient(s).`);
      form.reset();
      showBroadcastState();
    } catch (e) {
      sayError(status, e);
    }
  });
}
