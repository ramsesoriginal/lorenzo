// A dialog that fades out when it closes (docs/design/web, ADR 0415). The brand's `dialog` fades in
// by itself and a native close() is instant; an app that wants the fade out sets `data-closing`,
// waits for `animationend`, then closes. A reopen in the middle of a fade wins. This is the one
// place the pattern lives, for the drawer and, later, the palette and the shell's other dialogs.

/** Open a dialog as a modal, cancelling a fade-out that is under way. */
export function openDialog(dialog: HTMLDialogElement): void {
  dialog.removeAttribute('data-closing');
  if (!dialog.open) dialog.showModal();
}

/**
 * Close a dialog with the fade. With reduced motion the fade is as short as a frame, so this still
 * resolves; and if no animation ever fires (no CSS, a test without a layout engine) a timer
 * closes it anyway.
 */
export function closeDialog(dialog: HTMLDialogElement, fallbackMs = 400): void {
  if (!dialog.open || dialog.hasAttribute('data-closing')) return;

  dialog.setAttribute('data-closing', '');

  let done = false;
  const finish = () => {
    if (done || !dialog.hasAttribute('data-closing')) return;
    done = true;
    dialog.removeEventListener('animationend', onEnd);
    dialog.removeAttribute('data-closing');
    dialog.close();
  };
  const onEnd = (event: Event) => {
    if (event.target === dialog) finish();
  };

  dialog.addEventListener('animationend', onEnd);
  setTimeout(finish, fallbackMs);
}

/** Make Escape and a click on the backdrop use the fade too. */
export function fadeOnDismiss(dialog: HTMLDialogElement): void {
  dialog.addEventListener('cancel', (event) => {
    event.preventDefault();
    closeDialog(dialog);
  });
  dialog.addEventListener('click', (event) => {
    if (event.target === dialog) closeDialog(dialog);
  });
}
