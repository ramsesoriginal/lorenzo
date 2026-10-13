// Your personal access tokens (ADR 0269): name, when made, when last used, when it stops, and
// Revoke (asked first with window.confirm, like the other things that cannot be undone).

import { neverUsed, revokeTokenConfirmation, tokenState } from '../../lib/personalTokens';
import { listPersonalTokens, revokePersonalToken } from '../../lib/personalTokensApi';
import { formatTimestamp, relativeTime } from '../../lib/relativeTime';
import { say, sayError } from '../../lib/statusLine';
import { fromTemplate, requiredIn, rootElement } from '../../lib/template';
import type { PersonalTokenOut } from '../../lib/types';

const required = requiredIn('Personal access tokens');

function tokenRow(root: HTMLElement, token: PersonalTokenOut, onChanged: () => void): HTMLElement {
  const fragment = fromTemplate(root, '[data-token-template]');
  const revoke = required<HTMLButtonElement>(fragment, '[data-revoke]');
  const status = required<HTMLElement>(fragment, '[data-status]');
  const now = new Date();

  required<HTMLElement>(fragment, '[data-name]').textContent = token.name;
  required<HTMLElement>(fragment, '[data-state]').textContent =
    tokenState(token) === 'expired' ? 'Expired' : 'Active';

  const used = neverUsed(token)
    ? 'Never used'
    : `Last used ${relativeTime(token.last_used_at ?? '', now)}`;
  const stops = token.expires_at
    ? `${tokenState(token) === 'expired' ? 'Expired' : 'Expires'} ${formatTimestamp(token.expires_at)}`
    : 'Never expires';

  required<HTMLElement>(fragment, '[data-meta]').textContent =
    `…${token.hint} · Created ${formatTimestamp(token.created_at)} · ${used} · ${stops}`;

  revoke.addEventListener('click', async () => {
    if (!window.confirm(revokeTokenConfirmation(token.name))) return;

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
