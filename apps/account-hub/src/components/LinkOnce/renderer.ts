// What follows creating a link: the link itself, once. Also the result screen
// of /setup (ADR 0180), which says its own `notice` and `label`.

import { LINK_SHOWN_ONCE_NOTICE } from '../../lib/inviteLink';
import { say, sayError } from '../../lib/statusLine';
import { requiredIn } from '../../lib/template';

const required = requiredIn('Link once');

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

export type LinkOnceOptions = {
  url: string;
  onDismiss: () => void;
  notice?: string;
  label?: string;
};

// `root` is the <LinkOnce /> box.
export function renderLinkOnce(
  root: HTMLElement,
  { url, onDismiss, notice = LINK_SHOWN_ONCE_NOTICE, label = 'Invite link' }: LinkOnceOptions,
): void {
  const input = required<HTMLInputElement>(root, '[data-input]');
  const status = required<HTMLElement>(root, '[data-status]');

  input.value = url;
  input.setAttribute('aria-label', label);
  required<HTMLElement>(root, '[data-notice]').textContent = notice;

  required<HTMLButtonElement>(root, '[data-copy]').addEventListener('click', async () => {
    try {
      await copyText(url, input);
      say(status, 'Copied.');
    } catch (e) {
      sayError(status, e);
    }
  });

  required<HTMLButtonElement>(root, '[data-done]').addEventListener('click', () => {
    // The only copy of the link on the page goes with the box.
    input.value = '';
    onDismiss();
  });

  queueMicrotask(() => input.select());
}
