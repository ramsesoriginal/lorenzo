// /join (ADR 0171, 0220): read the invite token from the address, say what the link offers, and let a
// logged-in person take it. The token is never logged, put in a link, or kept anywhere but this
// tab's sessionStorage, until it is used. A link is for a campaign, for a role in a library or
// repository, or to share a repository with a library of the visitor's; the page branches on the
// kind the preview says.

import { ApiError } from '../../lib/apiError';
import { isAuthConfigured, isAuthenticated, login } from '../../lib/auth';
import { GM_WORDS, type GmWords, gmWords } from '../../lib/gmTitle';
import {
  DEAD_LINK_MESSAGE,
  forgetInviteToken,
  type InvitePreview,
  joinedMessageFor,
  NO_SHARE_TARGET_MESSAGE,
  offerFor,
  pastedInvite,
  readInviteToken,
  rememberInviteToken,
  type ShareTarget,
  shareTargets,
  storedInviteToken,
} from '../../lib/inviteLink';
import { previewInvite, redeemInvite } from '../../lib/invites';
import { getManaged, getMe } from '../../lib/me';
import { fetchPictureUrl } from '../../lib/pictureFetch';
import { browserSessionStorage } from '../../lib/returnPath';
import { say, sayError } from '../../lib/statusLine';
import { requiredIn } from '../../lib/template';
import { canCreateTenants, tenantHref } from '../../lib/tenantKind';
import { getCampaign } from '../../lib/tenants';
import type { InviteRedeemOut } from '../../lib/types';

const required = requiredIn('Join invite');

// A repository's picture is for a signed-in user unless the repository is public (ADR 0300). Someone
// logged in has it fetched with the token; someone who is not asks for it as it is, which a public
// repository answers and a private one does not, so there is no picture for them. Any other
// picture is open and shown from its address.
async function showInvitePicture(
  img: HTMLImageElement,
  address: string,
  ofRepository: boolean,
): Promise<void> {
  if (ofRepository && isAuthConfigured() && (await isAuthenticated())) {
    try {
      img.src = await fetchPictureUrl(new URL(address).pathname);
    } catch {
      // No picture; the name and the offer stand.
    }

    return;
  }

  img.src = address;
}

// Every dead link is the same 404, and the page does not tell them apart.
function isDead(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
}

// What the campaign a visitor has just become a GM of calls its game master (ADR 0294): the
// invite's preview could not say it before they joined, the campaign can once it is theirs to read.
// Without it (another kind of link, or a campaign that can't be read just now) it is "GM".
async function gmWordsOf(joined: InviteRedeemOut): Promise<GmWords> {
  if (joined.role !== 'gm' || joined.campaign_id === null) return GM_WORDS;

  try {
    return gmWords([await getCampaign(joined.tenant_id, joined.campaign_id)]);
  } catch {
    return GM_WORDS;
  }
}

// Where to go on once a link has been used.
function nextStep(
  preview: InvitePreview,
  joined: InviteRedeemOut,
  target: ShareTarget | null,
): { href: string; label: string } {
  if (preview.kind === 'library_access') {
    return {
      href: target === null ? '/tenants/' : tenantHref(target.id),
      label: 'Open your library',
    };
  }

  if (preview.kind === 'tenant_role') {
    return preview.tenant_kind === 'repository'
      ? { href: `/studio/?repository=${encodeURIComponent(joined.tenant_id)}`, label: 'Open it' }
      : { href: tenantHref(joined.tenant_id), label: 'Open it' };
  }

  return { href: '/campaigns/', label: 'Your campaigns' };
}

// `root` is the <JoinInvite /> block. It shows itself once there is something to say; a failure that
// is not a dead link rejects, for the page to show.
export async function renderJoinInvite(root: HTMLElement): Promise<void> {
  const dead = required<HTMLElement>(root, '[data-dead]');
  const invite = required<HTMLElement>(root, '[data-invite]');
  const picture = required<HTMLImageElement>(root, '[data-picture]');
  const name = required<HTMLElement>(root, '[data-campaign]');
  const offer = required<HTMLElement>(root, '[data-offer]');
  const share = required<HTMLElement>(root, '[data-share]');
  const library = required<HTMLSelectElement>(root, '[data-library]');
  const noLibrary = required<HTMLElement>(root, '[data-no-library]');
  const makeLibrary = required<HTMLElement>(root, '[data-make-library]');
  const loginButton = required<HTMLButtonElement>(root, '[data-login]');
  const joinButton = required<HTMLButtonElement>(root, '[data-join-button]');
  const next = required<HTMLAnchorElement>(root, '[data-next]');
  const keepHint = required<HTMLElement>(root, '[data-keep-hint]');
  const status = required<HTMLElement>(root, '[data-status]');
  const paste = required<HTMLElement>(root, '[data-paste]');
  const pasteForm = required<HTMLFormElement>(root, '[data-paste-form]');
  const pasteInput = required<HTMLInputElement>(root, '[data-paste-input]');
  const pasteError = required<HTMLElement>(root, '[data-paste-error]');

  // Read the token, keep it for the login round trip, and take it out of the address bar and the
  // history entry before anything else happens (ADR 0092 requirement 7).
  const storage = browserSessionStorage();
  const hash = window.location.hash;
  const fromLink = readInviteToken(hash);
  const kept = fromLink === null ? true : rememberInviteToken(storage, fromLink);

  if (hash !== '') {
    window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}`);
  }

  const token = fromLink ?? storedInviteToken(storage);

  // A link pasted into this very tab changes only the fragment, which the browser does not load a
  // page for: start over, so it is read like any other.
  window.addEventListener('hashchange', () => window.location.reload());

  // A link or a code pasted here goes on as a link someone opened would.
  pasteForm.addEventListener('submit', (event) => {
    event.preventDefault();

    const result = pastedInvite(pasteInput.value, window.location.origin);

    if ('error' in result) {
      pasteError.textContent = result.error;
      pasteError.hidden = false;
      pasteInput.focus();

      return;
    }

    pasteError.hidden = true;
    pasteInput.value = '';
    window.location.assign(result.href);
  });

  function showDeadLink(): void {
    forgetInviteToken(storage);
    invite.hidden = true;
    dead.textContent = DEAD_LINK_MESSAGE;
    dead.hidden = false;
    paste.hidden = false;
    root.hidden = false;
  }

  // The libraries to choose from, for a link that shares a repository: the ones the visitor is
  // an Owner of. With none, the page says so and, if they may make one, where.
  async function showLibraryChoice(): Promise<ShareTarget[]> {
    const [managed, me] = await Promise.all([getManaged(), getMe()]);
    const targets = shareTargets(managed);

    library.replaceChildren(...targets.map((target) => new Option(target.label, target.id)));
    share.hidden = false;

    if (targets.length === 0) {
      noLibrary.textContent = NO_SHARE_TARGET_MESSAGE;
      noLibrary.hidden = false;
      makeLibrary.hidden = !canCreateTenants(me);
      library.hidden = true;
    }

    return targets;
  }

  async function showActions(currentToken: string, preview: InvitePreview): Promise<void> {
    if (!isAuthConfigured()) {
      say(status, 'Authgear is not configured for this app yet.');

      return;
    }

    if (!(await isAuthenticated())) {
      loginButton.hidden = false;
      loginButton.addEventListener('click', () => void login());
      keepHint.hidden = kept;

      return;
    }

    let targets: ShareTarget[] = [];

    if (preview.kind === 'library_access') {
      targets = await showLibraryChoice();

      if (targets.length === 0) return;
    }

    joinButton.textContent = offerFor(preview).actionLabel;
    joinButton.hidden = false;
    joinButton.addEventListener('click', async () => {
      joinButton.disabled = true;
      say(status, preview.kind === 'library_access' ? 'Sharing…' : 'Joining…');

      const chosen = targets.find((target) => target.id === library.value) ?? null;

      try {
        const joined = await redeemInvite(currentToken, chosen?.id);

        forgetInviteToken(storage);
        say(status, joinedMessageFor(preview, joined, chosen?.name ?? '', await gmWordsOf(joined)));
        joinButton.hidden = true;
        library.disabled = true;

        const step = nextStep(preview, joined, chosen);

        next.href = step.href;
        next.textContent = step.label;
        next.hidden = false;
      } catch (cause) {
        if (isDead(cause)) {
          showDeadLink();

          return;
        }

        joinButton.disabled = false;
        sayError(status, cause);
      }
    });
  }

  if (token === null) {
    showDeadLink();

    return;
  }

  try {
    const preview = await previewInvite(token);

    name.textContent = preview.name;
    // Every kind says what it offers before anyone is asked to log in (ADR 0177, 0220).
    offer.textContent = offerFor(preview).sentence;

    if (preview.picture_url) {
      picture.referrerPolicy = 'no-referrer';
      picture.addEventListener('load', () => {
        picture.hidden = false;
      });
      void showInvitePicture(picture, preview.picture_url, preview.tenant_kind === 'repository');
    }

    invite.hidden = false;
    root.hidden = false;
    // The buttons follow once it is known whether this person is logged in.
    void showActions(token, preview).catch((cause) => sayError(status, cause));
  } catch (cause) {
    if (!isDead(cause)) throw cause;

    showDeadLink();
  }
}
