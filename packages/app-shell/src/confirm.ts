// A confirmation (ADR 0415): for what cannot be undone or is large. It names what is lost, and its
// button says what it does, never a generic "Are you sure?". The largest asks for a name to be typed,
// and then the button stays disabled, with the reason beside it, until it is.

import { closeDialog, fadeOnDismiss, openDialog } from './dialog';

export type ConfirmOptions = {
  title: string;
  /** What is lost, in the words the person knows (counts included); a paragraph each. */
  body: string | string[];
  /** What the button does: "Delete 12 entries", "Sign out". */
  confirm: string;
  cancel?: string;
  danger?: boolean;
  /** If set, this must be typed before the button works. */
  typeToConfirm?: string;
};

let sequence = 0;

/** Resolves true when confirmed, false when cancelled or dismissed. */
export function confirmDialog(options: ConfirmOptions): Promise<boolean> {
  return new Promise((resolve) => {
    const id = `shell-confirm-${++sequence}`;
    const dialog = document.createElement('dialog');
    const grip = document.createElement('div');
    const title = document.createElement('h2');
    const actions = document.createElement('div');
    const cancel = document.createElement('button');
    const confirm = document.createElement('button');
    let settled = false;

    dialog.setAttribute('aria-labelledby', `${id}-title`);
    grip.className = 'sheet-grip';
    grip.setAttribute('aria-hidden', 'true');
    title.id = `${id}-title`;
    title.textContent = options.title;
    dialog.append(grip, title);

    for (const paragraph of Array.isArray(options.body) ? options.body : [options.body]) {
      const p = document.createElement('p');

      p.textContent = paragraph;
      dialog.append(p);
    }

    let input: HTMLInputElement | null = null;
    let reason: HTMLElement | null = null;

    if (options.typeToConfirm) {
      const label = document.createElement('label');

      label.className = 'field';
      const text = document.createElement('span');

      text.className = 'field-label';
      text.textContent = `Type “${options.typeToConfirm}” to confirm`;
      input = document.createElement('input');
      input.className = 'text-input';
      input.autocomplete = 'off';
      reason = document.createElement('p');
      reason.id = `${id}-reason`;
      reason.className = 'status-text';
      reason.textContent = `The button works once you have typed “${options.typeToConfirm}”.`;
      label.append(text, input);
      dialog.append(label, reason);
    }

    cancel.type = 'button';
    cancel.className = 'btn btn-secondary';
    cancel.textContent = options.cancel ?? 'Cancel';
    confirm.type = 'button';
    confirm.className = `btn ${options.danger ? 'btn-danger' : 'btn-primary'}`;
    confirm.textContent = options.confirm;
    actions.className = 'dialog-actions';
    actions.append(cancel, confirm);
    dialog.append(actions);

    const enabled = () => !options.typeToConfirm || input?.value === options.typeToConfirm;
    const sync = () => {
      confirm.setAttribute('aria-disabled', String(!enabled()));
      if (reason) confirm.setAttribute('aria-describedby', reason.id);
    };
    const finish = (value: boolean) => {
      if (settled) return;
      settled = true;
      closeDialog(dialog);
      // The fade is a few hundred milliseconds; the answer does not wait for it.
      setTimeout(() => dialog.remove(), 600);
      resolve(value);
    };

    confirm.addEventListener('click', () => {
      if (enabled()) finish(true);
    });
    cancel.addEventListener('click', () => finish(false));
    dialog.addEventListener('cancel', () => finish(false));
    dialog.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && event.target === input) {
        event.preventDefault();
        if (enabled()) finish(true);
      }
    });
    input?.addEventListener('input', sync);
    sync();

    document.body.append(dialog);
    fadeOnDismiss(dialog);
    openDialog(dialog);
    // The first field takes focus; with none, the safe choice does.
    (input ?? cancel).focus();
  });
}
