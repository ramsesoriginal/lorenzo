// The result of /setup (ADR 0180): the links, each shown once, and where to go next. "Done" clears a
// link from the page; nothing keeps it (ADR 0171's panel does the same).

import { GM_LINK_SHOWN_ONCE_NOTICE, inviteUrl, LINK_SHOWN_ONCE_NOTICE } from '../../lib/inviteLink';
import type { SetupInput, SetupState } from '../../lib/setup';
import { cloneRoot, requiredIn } from '../../lib/template';
import { tenantHref } from '../../lib/tenantKind';
import { renderLinkOnce } from '../LinkOnce/renderer';

const required = requiredIn('Setup');

// `root` is the <Setup /> block. `gmLabel` is who the person found, if they did.
export function showResult(
  root: HTMLElement,
  input: SetupInput,
  state: SetupState,
  gmLabel: string | null,
): void {
  required<HTMLElement>(root, '[data-summary]').textContent =
    `${input.campaignName} is in ${input.libraryName}.`;

  required<HTMLElement>(root, '[data-who]').textContent =
    input.gm.kind === 'me'
      ? "You're its GM."
      : input.gm.kind === 'user'
        ? `${gmLabel ?? 'The person you found'} is its GM.`
        : 'Send the GM link to the person who should run it.';

  // The library as it was just made, which /tenants opens by its id.
  if (state.libraryId !== null) {
    required<HTMLAnchorElement>(root, '[data-library-link]').href = tenantHref(state.libraryId);
  }

  // One link in its own box: the link, once, and Done takes the box away.
  function showLink(
    boxSelector: string,
    linkSelector: string,
    token: string | null,
    notice: string,
    label: string,
  ): void {
    if (token === null) return;

    const wrap = required<HTMLElement>(root, boxSelector);
    const box = required<HTMLElement>(wrap, linkSelector);
    const linkOnce = cloneRoot(root, '[data-link-once-template]');

    renderLinkOnce(linkOnce, {
      url: inviteUrl(window.location.origin, token),
      notice,
      label,
      onDismiss: () => {
        // The only copy of the link on the page goes with the box.
        box.replaceChildren();
        wrap.hidden = true;
      },
    });
    box.replaceChildren(linkOnce);
    wrap.hidden = false;
  }

  showLink(
    '[data-gm-link]',
    '[data-gm-link-box]',
    state.gmLinkToken,
    GM_LINK_SHOWN_ONCE_NOTICE,
    'GM invite link',
  );
  showLink(
    '[data-player-link]',
    '[data-player-link-box]',
    state.playerLinkToken,
    LINK_SHOWN_ONCE_NOTICE,
    'Link for your players',
  );
}
