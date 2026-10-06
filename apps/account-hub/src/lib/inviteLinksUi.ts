// The "link shown once" box that /setup (ADR 0180) still builds in code; a campaign's invite
// links themselves are the InviteLinks component, whose LinkOnce is this same box. A token exists
// exactly once, in the response to creating a link, and is shown whole in one element, nowhere else.
import { createStatusSpan } from './dom';
import { showError } from './errorUi';
import { LINK_SHOWN_ONCE_NOTICE } from './inviteLink';

async function copyText(text: string, source: HTMLInputElement): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    // No async clipboard (an insecure context, a blocked permission): leave the
    // link selected, ready for the person's own copy.
    source.select();
    throw new Error("Couldn't copy it for you. The link is selected: copy it yourself.");
  }
}

// What follows creating a link: the link itself, once. Also the result screen
// of /setup (ADR 0180), which says its own `notice` and `label`.
export function renderLinkOnce(
  url: string,
  onDismiss: () => void,
  notice: string = LINK_SHOWN_ONCE_NOTICE,
  label = 'Invite link',
): HTMLElement {
  const box = document.createElement('div');
  box.className = 'invite-link-once';
  box.setAttribute('role', 'status');

  const input = document.createElement('input');
  input.type = 'text';
  input.readOnly = true;
  input.className = 'invite-link-input';
  input.value = url;
  input.setAttribute('aria-label', label);

  const copy = document.createElement('button');
  copy.type = 'button';
  copy.textContent = 'Copy';
  const done = document.createElement('button');
  done.type = 'button';
  done.textContent = 'Done';
  const status = createStatusSpan();
  copy.addEventListener('click', async () => {
    try {
      await copyText(url, input);
      status.textContent = 'Copied.';
    } catch (e) {
      showError(status, e);
    }
  });
  done.addEventListener('click', () => {
    // The only copy of the link on the page goes with the box.
    input.value = '';
    onDismiss();
  });

  const noticeEl = document.createElement('p');
  noticeEl.textContent = notice;
  box.append(input, copy, done, status, noticeEl);
  queueMicrotask(() => input.select());
  return box;
}
