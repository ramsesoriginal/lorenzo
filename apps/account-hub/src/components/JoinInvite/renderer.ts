// /join (ADR 0171): read the invite token from the address, say what the link offers, and let a
// logged-in person take it. The token is never logged, put in a link, or kept anywhere but this
// tab's sessionStorage, until it is used.

import { ApiError } from '../../lib/apiError';
import { isAuthConfigured, isAuthenticated, login } from '../../lib/auth';
import { showError } from '../../lib/errorUi';
import {
  DEAD_LINK_MESSAGE,
  forgetInviteToken,
  type InviteRole,
  inviteOffer,
  joinedMessage,
  readInviteToken,
  rememberInviteToken,
  storedInviteToken,
} from '../../lib/inviteLink';
import { previewInvite, redeemInvite } from '../../lib/invites';
import { browserSessionStorage } from '../../lib/returnPath';
import { say, sayError } from '../../lib/statusLine';
import { requiredIn } from '../../lib/template';

const required = requiredIn('Join invite');

// Every dead link is the same 404, and the page does not tell them apart.
function isDead(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
}

// `root` is the <JoinInvite /> block. It shows itself once there is something to say; a failure that
// is not a dead link rejects, for the page to show.
export async function renderJoinInvite(root: HTMLElement): Promise<void> {
  const dead = required<HTMLElement>(root, '[data-dead]');
  const invite = required<HTMLElement>(root, '[data-invite]');
  const picture = required<HTMLImageElement>(root, '[data-picture]');
  const campaign = required<HTMLElement>(root, '[data-campaign]');
  const offer = required<HTMLElement>(root, '[data-offer]');
  const loginButton = required<HTMLButtonElement>(root, '[data-login]');
  const joinButton = required<HTMLButtonElement>(root, '[data-join-button]');
  const next = required<HTMLElement>(root, '[data-next]');
  const keepHint = required<HTMLElement>(root, '[data-keep-hint]');
  const status = required<HTMLElement>(root, '[data-status]');

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

  function showDeadLink(): void {
    forgetInviteToken(storage);
    invite.hidden = true;
    dead.textContent = DEAD_LINK_MESSAGE;
    dead.hidden = false;
    root.hidden = false;
  }

  async function showActions(currentToken: string, role: InviteRole, name: string): Promise<void> {
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

    joinButton.textContent = inviteOffer(role).joinLabel;
    joinButton.hidden = false;
    joinButton.addEventListener('click', async () => {
      joinButton.disabled = true;
      say(status, 'Joining…');

      try {
        const joined = await redeemInvite(currentToken);

        forgetInviteToken(storage);
        say(status, joinedMessage(name, joined.already_joined, joined.role));
        joinButton.hidden = true;
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

    campaign.textContent = preview.campaign_name;
    // A GM link says so before anyone is asked to log in (ADR 0177).
    offer.textContent = inviteOffer(preview.role).sentence;

    if (preview.picture_url) {
      picture.src = preview.picture_url;
      picture.referrerPolicy = 'no-referrer';
      picture.addEventListener('load', () => {
        picture.hidden = false;
      });
    }

    invite.hidden = false;
    root.hidden = false;
    // The buttons follow once it is known whether this person is logged in.
    void showActions(token, preview.role, preview.campaign_name).catch((cause) =>
      sayError(status, cause),
    );
  } catch (cause) {
    if (!isDead(cause)) throw cause;

    showDeadLink();
  }
}
