// Notification composer, shared by tenant-scope and campaign-scope
// sending (RFC 0017 (g)). The ADR 0074 picker is an *optional* recipient
// resolver here - leaving it empty broadcasts to the scope's whole
// roster, matching NotificationCreate's own documented behavior rather
// than requiring a recipient. Character-scope and group-scope sending are
// deliberately not offered - this app has no character/group management
// surface for a GM to pick a sensible target from yet.

import { displayNameFor } from './format';
import type { Notification, NotificationCreate, UserRefOut } from './types';
import { mountUserPicker } from './userPicker';

export function renderNotificationComposer(
  send: (body: NotificationCreate) => Promise<Notification[]>,
): HTMLElement {
  const container = document.createElement('div');
  const heading = document.createElement('p');
  heading.textContent = 'Send a notification:';
  container.append(heading);

  const form = document.createElement('form');
  const typeInput = document.createElement('input');
  typeInput.type = 'text';
  typeInput.placeholder = 'Type (e.g. announcement)';
  typeInput.required = true;
  const titleInput = document.createElement('input');
  titleInput.type = 'text';
  titleInput.placeholder = 'Title';
  titleInput.required = true;
  const bodyInput = document.createElement('textarea');
  bodyInput.placeholder = 'Body';
  bodyInput.required = true;
  form.append(typeInput, titleInput, bodyInput);

  let recipient: UserRefOut | null = null;
  const recipientArea = document.createElement('div');
  const recipientStatus = document.createElement('span');
  recipientStatus.className = 'status-text';

  function showBroadcastState() {
    recipient = null;
    const pickButton = document.createElement('button');
    pickButton.type = 'button';
    pickButton.textContent = 'Pick a specific recipient instead of broadcasting';
    pickButton.addEventListener('click', () => {
      recipientArea.replaceChildren();
      mountUserPicker(recipientArea, (user) => {
        recipient = user;
        showRecipientState(user);
      });
    });
    recipientArea.replaceChildren(
      Object.assign(document.createElement('p'), {
        className: 'status-text',
        textContent: 'Broadcasting to everyone in this scope.',
      }),
      pickButton,
    );
  }

  function showRecipientState(user: UserRefOut) {
    const clearButton = document.createElement('button');
    clearButton.type = 'button';
    clearButton.textContent = 'Clear (broadcast instead)';
    clearButton.addEventListener('click', showBroadcastState);
    recipientArea.replaceChildren(
      Object.assign(document.createElement('p'), {
        textContent: `Sending to: ${displayNameFor({ ...user, user_id: user.id })}`,
      }),
      clearButton,
    );
  }

  showBroadcastState();
  form.append(recipientArea);

  const button = document.createElement('button');
  button.type = 'submit';
  button.textContent = 'Send';
  form.append(button, recipientStatus);

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    recipientStatus.textContent = 'Sending…';
    try {
      const sent = await send({
        recipient_user_id: recipient?.id ?? null,
        type: typeInput.value.trim(),
        title: titleInput.value.trim(),
        body: bodyInput.value.trim(),
      });
      recipientStatus.textContent = `Sent to ${sent.length} recipient(s).`;
      form.reset();
      showBroadcastState();
    } catch (e) {
      recipientStatus.textContent = e instanceof Error ? e.message : String(e);
    }
  });

  container.append(form);
  return container;
}
