// A single shared "resolve a person to a user_id" widget (ADR 0074): an email-or-nickname lookup,
// reused by the GM-assignment, player-invite, notification and membership slices (RFC 0014)
// rather than each building the same form.

import { say, sayError } from '../../lib/statusLine';
import { requiredIn } from '../../lib/template';
import type { UserRefOut } from '../../lib/types';
import { findUserByEmail, findUserByNickname } from '../../lib/users';

const required = requiredIn('User picker');

// Several pickers can share a page, and radios only group by name.
let pickers = 0;

// `root` is the <UserPicker /> form itself.
export function renderUserPicker(root: HTMLElement, onResolved: (user: UserRefOut) => void): void {
  const emailRadio = required<HTMLInputElement>(root, '[data-email]');
  const nicknameRadio = required<HTMLInputElement>(root, '[data-nickname]');
  const input = required<HTMLInputElement>(root, '[data-lookup]');
  const status = required<HTMLElement>(root, '[data-status]');

  pickers += 1;
  emailRadio.name = `user-picker-${pickers}-lookup-type`;
  nicknameRadio.name = emailRadio.name;

  root.addEventListener('submit', async (event) => {
    event.preventDefault();
    const value = input.value.trim();
    if (value === '') return;
    say(status, 'Looking up…');
    try {
      const user = nicknameRadio.checked
        ? await findUserByNickname(value)
        : await findUserByEmail(value);
      if (user === null) {
        say(status, 'No user found with that email/nickname.');
        return;
      }
      say(status, `Found: ${user.display_name ?? user.nickname ?? user.id}`);
      onResolved(user);
    } catch (e) {
      sayError(status, e);
    }
  });
}
