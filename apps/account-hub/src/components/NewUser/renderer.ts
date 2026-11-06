// What someone who belongs nowhere yet is offered: start a table, if the account may (ADR 0175),
// or join one by an invite link or just its code, which goes on to /join as a link someone
// opened would.

import { showsDiscover } from '../../lib/discover';
import { getFacets } from '../../lib/discoverApi';
import { pastedInvite } from '../../lib/inviteLink';
import { requiredIn } from '../../lib/template';
import { canCreateTenants } from '../../lib/tenantKind';
import type { MeOut } from '../../lib/types';

const required = requiredIn('New user');

// The mascot: the illustrators' image, then the earlier one, then a placeholder with the words (the
// meaning is in the words either way).
function showArt(root: HTMLElement): void {
  const art = required<HTMLElement>(root, '[data-art]');
  const image = required<HTMLImageElement>(art, '[data-art-image]');
  const fallback = image.dataset.artFallback ?? '';
  let triedFallback = false;

  image.addEventListener('error', () => {
    if (!triedFallback && fallback) {
      triedFallback = true;
      image.src = fallback;

      return;
    }
    art.dataset.missing = '';
    art.replaceChildren(document.createTextNode(image.alt));
  });
  image.src = image.dataset.artSrc ?? fallback;
}

// `root` is the <NewUser /> block; it shows itself.
export function renderNewUser(root: HTMLElement, me: MeOut): void {
  const mayCreate = canCreateTenants(me);
  const form = required<HTMLFormElement>(root, '[data-invite-form]');
  const input = required<HTMLInputElement>(root, '[data-invite-input]');
  const error = required<HTMLElement>(root, '[data-invite-error]');

  required<HTMLElement>(root, '[data-start-card]').hidden = !mayCreate;
  required<HTMLElement>(root, '[data-can-create]').hidden = !mayCreate;
  required<HTMLElement>(root, '[data-cannot-create]').hidden = mayCreate;

  showArt(root);

  // Browsing public repositories is offered only where they are on (ADR 0290).
  void getFacets().then(
    (facets) => {
      required<HTMLElement>(root, '[data-browse]').hidden = !showsDiscover(facets);
    },
    () => {},
  );

  form.addEventListener('submit', (event) => {
    event.preventDefault();

    const result = pastedInvite(input.value, window.location.origin);

    if ('error' in result) {
      error.textContent = result.error;
      error.hidden = false;
      input.focus();

      return;
    }

    error.hidden = true;
    input.value = '';
    window.location.assign(result.href);
  });

  root.hidden = false;
}
