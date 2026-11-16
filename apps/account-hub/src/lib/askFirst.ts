// Asking first, before something that cannot be undone or is large (ADR 0415, D26): a dialog of the
// shell that names what is lost, with a button that says what it does. The question is the message's
// first sentence, up to its question mark; the rest is what is lost. Where the shell is not there
// (a page that did not start it), the browser's own confirm still asks.
import { currentShell } from './shell';

export type Ask = {
  /** What the button does: "Leave", "Revoke link". */
  confirm: string;
  cancel?: string;
};

/** Resolves true when the person agrees. */
export async function askFirst(message: string, ask: Ask): Promise<boolean> {
  const shell = currentShell();

  if (!shell) return window.confirm(message);

  const cut = message.indexOf('?');

  return shell.confirm({
    title: cut === -1 ? message : message.slice(0, cut + 1),
    body: cut === -1 ? '' : message.slice(cut + 1).trim(),
    confirm: ask.confirm,
    cancel: ask.cancel ?? 'Cancel',
    danger: true,
  });
}
