// Your personal access tokens (ADR 0269, ADR 0418): the name and the last four characters, a state in
// words with an icon, and Revoke (asked first in a dialog that names what happens).

import { describeToken, revokeTokenConfirmation } from '../../lib/personalTokens';
import { listPersonalTokens, revokePersonalToken } from '../../lib/personalTokensApi';
import { currentShell } from '../../lib/shell';
import { say, sayError } from '../../lib/statusLine';
import { fromTemplate, requiredIn, rootElement } from '../../lib/template';
import type { PersonalTokenOut } from '../../lib/types';

const required = requiredIn('Personal access tokens');

function tokenRow(root: HTMLElement, token: PersonalTokenOut, onChanged: () => void): HTMLElement {
  const fragment = fromTemplate(root, '[data-token-template]');
  const revoke = required<HTMLButtonElement>(fragment, '[data-revoke]');
  const status = required<HTMLElement>(fragment, '[data-status]');
  const row = fragment.querySelector<HTMLElement>('.token-row');
  const description = describeToken(token, new Date());

  required<HTMLElement>(fragment, '[data-name]').textContent = token.name;
  required<HTMLElement>(fragment, '[data-hint]').textContent = token.hint;
  required<HTMLElement>(fragment, '[data-used]').textContent = description.used;
  required<HTMLElement>(fragment, '[data-note]').textContent = description.note;
  if (row) row.dataset.tone = description.tone;

  const icon = fragment.querySelector('[data-icon]');
  const href = icon?.getAttribute('href');

  if (icon && href) icon.setAttribute('href', `${href.split('#')[0]}#icon-${description.icon}`);

  // A token that stops is named, and what happens is said, before it is asked (ADR 0418, D26).
  revoke.addEventListener('click', async () => {
    const shell = currentShell();
    const yes = shell
      ? await shell.confirm({
          title: `Revoke “${token.name}”?`,
          body: revokeTokenConfirmation(token.name),
          confirm: 'Revoke',
          cancel: 'Keep it',
          danger: true,
        })
      : window.confirm(revokeTokenConfirmation(token.name));

    if (!yes) return;

    revoke.disabled = true;
    say(status, 'Revoking…');

    try {
      await revokePersonalToken(token.id);
      onChanged();
    } catch (cause) {
      revoke.disabled = false;
      sayError(status, cause);
    }
  });

  return rootElement(fragment);
}

// `root` is the <PersonalTokens /> section; it shows itself.
export function renderPersonalTokens(root: HTMLElement): void {
  const listStatus = required<HTMLElement>(root, '[data-list-status]');
  const list = required<HTMLElement>(root, '[data-list]');

  async function refresh(): Promise<void> {
    try {
      const tokens = await listPersonalTokens();

      say(listStatus, tokens.length === 0 ? 'No tokens yet.' : '');
      list.replaceChildren(...tokens.map((token) => tokenRow(root, token, () => void refresh())));
    } catch (cause) {
      sayError(listStatus, cause);
    }
  }

  root.hidden = false;
  void refresh();
}
