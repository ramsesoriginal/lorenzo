import type { UserRefOut } from './types';
import { findUserByEmail, findUserByNickname } from './users';

// A single shared "resolve a person to a user_id" widget - built once here
// (vanilla TS, no component framework, per ADR 0071) and reused unmodified
// by the GM-assignment and player-invite sub-slices (RFC 0014), rather
// than each rebuilding the same email-or-nickname lookup UI.
export function mountUserPicker(
  container: HTMLElement,
  onResolved: (user: UserRefOut) => void,
): void {
  const form = document.createElement('form');

  const emailRadio = document.createElement('input');
  emailRadio.type = 'radio';
  emailRadio.name = `${crypto.randomUUID()}-lookup-type`;
  emailRadio.value = 'email';
  emailRadio.checked = true;
  const emailLabel = document.createElement('label');
  emailLabel.append(emailRadio, 'Email');

  const nicknameRadio = document.createElement('input');
  nicknameRadio.type = 'radio';
  nicknameRadio.name = emailRadio.name;
  nicknameRadio.value = 'nickname';
  const nicknameLabel = document.createElement('label');
  nicknameLabel.append(nicknameRadio, 'Nickname');

  const input = document.createElement('input');
  input.type = 'text';
  input.placeholder = 'Email or nickname';
  input.required = true;

  const button = document.createElement('button');
  button.type = 'submit';
  button.textContent = 'Look up';

  const status = document.createElement('span');
  status.setAttribute('role', 'status');

  form.append(emailLabel, nicknameLabel, input, button, status);
  container.append(form);

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const value = input.value.trim();
    if (value === '') return;
    status.textContent = 'Looking up&hellip;';
    try {
      const user = nicknameRadio.checked
        ? await findUserByNickname(value)
        : await findUserByEmail(value);
      if (user === null) {
        status.textContent = 'No user found with that email/nickname.';
        return;
      }
      status.textContent = `Found: ${user.display_name ?? user.nickname ?? user.id}`;
      onResolved(user);
    } catch (e) {
      status.textContent = e instanceof Error ? e.message : String(e);
    }
  });
}
