// Signing out (W-H): with changes that were never sent, it says plainly that they are only here and
// what each way out does. With none, there is nothing to say and it signs out.
//
// What Bench keeps on this device is, so far, only what is waiting to be sent (it is held in the
// page, not stored: B4 makes it survive a closed tab); signing out or closing the page loses it.

import type { Bench } from '../core/bench';

const el = <K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};

const changes = (n: number) => `${n} ${n === 1 ? 'change' : 'changes'}`;

/** Signs out, after asking if there is something to lose. */
export function requestSignOut(bench: Bench, signOut: () => void | Promise<void>): void {
  if (!bench.outbox.length) {
    void signOut();
    return;
  }
  const dialog = el('dialog', 'confirm');
  dialog.setAttribute('aria-labelledby', 'sign-out-title');
  const body = el('div', 'confirm-body');
  dialog.append(body);
  let busy = false;

  const close = () => {
    dialog.close();
    dialog.remove();
  };

  const draw = () => {
    const rows = bench.unsent();
    const total = rows.reduce((n, r) => n + r.count, 0);
    // Everything went while the dialog was open (it was sent): nothing is left to lose.
    if (!total && !busy) {
      close();
      void signOut();
      return;
    }
    const title = el('h2', undefined, `Sign out with ${changes(total)} not sent?`);
    title.id = 'sign-out-title';
    const list = el('ul', 'confirm-list');
    for (const r of rows) {
      const li = el('li');
      li.append(
        el('span', undefined, r.name || 'A new entry'),
        el('span', 'muted', changes(r.count)),
      );
      list.append(li);
    }
    const problems = bench.outbox.filter((c) => c.state === 'conflict' || c.state === 'attention');
    const note = el(
      'p',
      'muted',
      bench.offline
        ? 'There is no connection, so they cannot be sent right now.'
        : problems.length
          ? `${changes(problems.length)} could not be sent and need${problems.length === 1 ? 's' : ''} a look first: open the entry, or give them up.`
          : '',
    );
    note.hidden = !note.textContent;

    const actions = el('div', 'actions');
    const send = el('button', 'btn primary', 'Send them, then sign out');
    send.type = 'button';
    send.disabled = busy || bench.offline;
    send.addEventListener('click', async () => {
      busy = true;
      draw();
      await bench.run();
      busy = false;
      draw();
    });
    const give = el('button', 'btn', 'Give them up and sign out');
    give.type = 'button';
    give.disabled = busy;
    give.addEventListener('click', async () => {
      busy = true;
      await bench.discardUnsent();
      busy = false;
      close();
      void signOut();
    });
    const cancel = el('button', 'btn', 'Cancel');
    cancel.type = 'button';
    cancel.addEventListener('click', close);
    actions.append(send, give, cancel);

    body.replaceChildren(
      title,
      el(
        'p',
        undefined,
        'These changes are only on this device. Signing out loses them, so they have to be sent first or given up.',
      ),
      list,
      note,
      actions,
    );
  };

  dialog.addEventListener('cancel', close); // Escape
  document.body.append(dialog);
  draw();
  // After the key press that asked for it has finished: its Enter would otherwise press whatever
  // button has the focus by then, and one of them gives the changes up.
  setTimeout(() => {
    dialog.showModal();
    // Never the button that loses changes; the one that sends them if it can, else Cancel.
    const send = dialog.querySelector<HTMLButtonElement>('.primary');
    const cancel = [...dialog.querySelectorAll('button')].find((b) => b.textContent === 'Cancel');
    (send && !send.disabled ? send : cancel)?.focus();
  }, 0);
}

/** Closing the page with changes not sent asks first (the browser words it itself). */
export function guardUnsent(bench: () => Bench): void {
  window.addEventListener('beforeunload', (ev) => {
    if (bench().outbox.length) ev.preventDefault();
  });
}
