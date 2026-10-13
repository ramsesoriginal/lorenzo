// Deleting a library or a repository (ADR 0267, the route of ADR 0184). An Owner whose account may
// delete gets a button; it opens a dialog that says what is lost (counts read when it opens, one
// request for the entries, the rest from what the tab already holds), and asks for the name to be
// typed before the last button works. Anyone else who sees the section is told why there is none.
// On success the hub's cache is emptied and the page is told, to leave for the list.

import { clearCache } from '../../lib/cache';
import {
  deletedMessage,
  deleteFootnote,
  deleteIntro,
  deleteStanding,
  type Losses,
  lossLines,
  nameMatches,
  refusalMessage,
  standingNote,
  typeNamePrompt,
} from '../../lib/deleting';
import { describeError } from '../../lib/describeError';
import { countEntries } from '../../lib/entities';
import { say } from '../../lib/statusLine';
import { requiredIn } from '../../lib/template';
import { kindNoun } from '../../lib/tenantKind';
import { deleteTenant } from '../../lib/tenants';
import type { TenantSummaryOut } from '../../lib/types';

const required = requiredIn('Tenant delete');

export type RenderedTenantDelete = {
  // The section for `tenant`. `known` is what the tab already holds (campaigns, people); null is
  // not claimed. Whether `accountMayDelete` is the platform permission of ADR 0184.
  show(
    tenant: TenantSummaryOut,
    options: { accountMayDelete: boolean; known: Pick<Losses, 'campaigns' | 'people'> },
  ): void;
  hide(): void;
};

// `root` is the <TenantDelete /> section. `onDeleted` hears of the message to show where the person
// lands.
export function renderTenantDelete(
  root: HTMLElement,
  onDeleted: (message: string, tenant: TenantSummaryOut) => void,
): RenderedTenantDelete {
  const heading = required<HTMLElement>(root, '[data-heading]');
  const note = required<HTMLElement>(root, '[data-note]');
  const openRow = required<HTMLElement>(root, '[data-open-row]');
  const open = required<HTMLButtonElement>(root, '[data-open]');
  const status = required<HTMLElement>(root, '[data-status]');
  const dialog = required<HTMLDialogElement>(root, '[data-delete-dialog]');
  const form = required<HTMLFormElement>(dialog, '[data-delete-form]');
  const title = required<HTMLElement>(dialog, '[data-dialog-title]');
  const intro = required<HTMLElement>(dialog, '[data-dialog-intro]');
  const lostHeading = required<HTMLElement>(dialog, '[data-dialog-lost-heading]');
  const lost = required<HTMLElement>(dialog, '[data-dialog-lost]');
  const footnote = required<HTMLElement>(dialog, '[data-dialog-footnote]');
  const label = required<HTMLElement>(dialog, '[data-confirm-label]');
  const input = required<HTMLInputElement>(dialog, '[data-confirm-input]');
  const error = required<HTMLElement>(dialog, '[data-dialog-error]');
  const cancel = required<HTMLButtonElement>(dialog, '[data-dialog-cancel]');
  const confirm = required<HTMLButtonElement>(dialog, '[data-dialog-confirm]');

  let tenant: TenantSummaryOut | null = null;
  let known: Pick<Losses, 'campaigns' | 'people'> = { campaigns: null, people: null };
  // Counts the tenants shown, so an answer that arrives for an earlier one is dropped.
  let shown = 0;
  let deleting = false;

  function sync(): void {
    confirm.disabled = deleting || !tenant || !nameMatches(input.value, tenant.name);
  }

  input.addEventListener('input', sync);

  // Closing by Escape or the Cancel button, never while the request is on its way: a delete that was
  // sent cannot be called back, so the dialog stays to say how it went.
  dialog.addEventListener('cancel', (event) => {
    if (deleting) event.preventDefault();
  });
  cancel.addEventListener('click', () => {
    if (!deleting) dialog.close();
  });
  dialog.addEventListener('close', () => {
    input.value = '';
    sync();

    if (!deleting) open.focus();
  });

  open.addEventListener('click', async () => {
    const target = tenant;
    const turn = shown;

    if (!target) return;

    open.disabled = true;
    say(status, 'Counting what is in it…');

    let entries: number | null = null;

    try {
      entries = await countEntries(target.id);
    } catch {
      // Not claimed: the dialog still says what it can.
    }

    open.disabled = false;

    if (turn !== shown) return;

    say(status, '');
    title.textContent = `Delete this ${kindNoun(target.kind)}?`;
    intro.textContent = deleteIntro(target.name);

    const lines = lossLines({
      campaigns: target.kind === 'repository' ? null : known.campaigns,
      entries,
      people: known.people,
    });

    lost.replaceChildren(
      ...lines.map((line) => {
        const item = document.createElement('li');

        item.textContent = line;

        return item;
      }),
    );
    lostHeading.hidden = lines.length === 0;
    footnote.textContent = deleteFootnote(target.kind);
    label.textContent = typeNamePrompt(target.name);
    confirm.textContent = `Delete this ${kindNoun(target.kind)}`;
    error.hidden = true;
    input.value = '';
    sync();
    dialog.showModal();
    input.focus();
  });

  form.addEventListener('submit', (event) => {
    event.preventDefault();

    const target = tenant;

    if (!target || deleting || !nameMatches(input.value, target.name)) return;

    deleting = true;
    error.hidden = true;
    cancel.disabled = true;
    input.disabled = true;
    sync();

    void (async () => {
      try {
        await deleteTenant(target.id);
      } catch (cause) {
        deleting = false;
        cancel.disabled = false;
        input.disabled = false;
        sync();
        error.hidden = false;
        // The refusals in the words of this page; anything else in the API's own.
        error.textContent = refusalMessage(cause, target.kind) ?? describeError(cause);
        input.focus();

        return;
      }

      // What the hub holds is of a library that is gone.
      clearCache();
      deleting = false;
      cancel.disabled = false;
      input.disabled = false;
      dialog.close();
      onDeleted(deletedMessage(target.name, target.kind), target);
    })();
  });

  return {
    show(next, options) {
      shown += 1;
      tenant = next;
      known = options.known;
      deleting = false;

      if (dialog.open) dialog.close();

      const standing = deleteStanding(next, options.accountMayDelete);
      const sentence = standingNote(standing, next.kind);

      heading.textContent = `Delete this ${kindNoun(next.kind)}`;
      open.textContent = `Delete this ${kindNoun(next.kind)}…`;
      note.textContent = sentence ?? '';
      note.hidden = sentence === null;
      openRow.hidden = standing !== 'allowed';
      open.disabled = false;
      say(status, '');
      root.hidden = standing === 'none';
    },

    hide() {
      shown += 1;
      tenant = null;

      if (dialog.open) dialog.close();

      root.hidden = true;
    },
  };
}
