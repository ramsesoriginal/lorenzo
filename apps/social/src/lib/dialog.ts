import { closeDialog, fadeOnDismiss, openDialog } from '@lorenzo/app-shell';
import { actions, button, el, message, submit } from './dom';

/**
 * A small form in a dialog: it opens, `run` does the work on submit, a refusal is said inside
 * and the dialog stays; success closes it. Resolves when the dialog is gone.
 */
export function formDialog(options: {
  title: string;
  submit: string;
  fields: HTMLElement[];
  run(): Promise<void>;
}): Promise<void> {
  return new Promise((resolve) => {
    const dialog = el('dialog', '', 'dialog');
    const form = el('form', '', 'stack');
    form.setAttribute('aria-label', options.title);
    const failure = el('p', '', 'error-text');
    failure.setAttribute('role', 'alert');
    const cancel = button('Cancel', () => closeDialog(dialog), { variant: 'secondary' });
    const go = submit(options.submit);
    form.append(el('h2', options.title), ...options.fields, failure, actions(cancel, go));
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      failure.textContent = '';
      go.disabled = true;
      options
        .run()
        .then(() => closeDialog(dialog))
        .catch((error) => {
          failure.textContent = message(error);
        })
        .finally(() => {
          go.disabled = false;
        });
    });
    dialog.addEventListener('close', () => {
      dialog.remove();
      resolve();
    });
    fadeOnDismiss(dialog);
    dialog.append(form);
    document.body.append(dialog);
    openDialog(dialog);
    dialog.querySelector<HTMLInputElement>('input')?.focus();
  });
}

/** A dialog that stays open while its parts act: a title, what it holds, and a Close button. */
export function panelDialog(title: string, body: HTMLElement[], onClose?: () => void) {
  const dialog = el('dialog', '', 'dialog');
  const box = el('div', '', 'stack');
  box.setAttribute('role', 'group');
  box.setAttribute('aria-label', title);
  const close = button('Close', () => closeDialog(dialog), { variant: 'secondary' });
  box.append(el('h2', title), ...body, actions(close));
  dialog.addEventListener('close', () => {
    dialog.remove();
    onClose?.();
  });
  fadeOnDismiss(dialog);
  dialog.append(box);
  document.body.append(dialog);
  openDialog(dialog);
  return dialog;
}
