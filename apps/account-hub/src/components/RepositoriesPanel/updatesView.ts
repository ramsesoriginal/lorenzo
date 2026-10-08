// One repository's updates (ADR 0203, RFC 0036 §3): what it changed since the library copied or
// last updated it, in groups (conflicts, changed, new, removed upstream, and the parents it added
// or took off), each row with its change in words and what to do about it. Nothing is applied until
// a button says so; "apply all clean" is checked first and shown as a receipt. The choices (which
// conflict to keep, how to settle a name clash, what was skipped) live in the page, in `state`.

import { type Choice, choiceProblem, collisionKey } from '../../lib/copyWizard';
import { describeError } from '../../lib/describeError';
import { applyUpdates, getUpdates } from '../../lib/repositories';
import { shelfHref } from '../../lib/shelf';
import { sayError } from '../../lib/statusLine';
import { cloneRoot, requiredIn } from '../../lib/template';
import type {
  AddedOut,
  ApplyUpdatesOut,
  ApplyUpdatesRequest,
  AttachmentAddedOut,
  AttachmentRefOut,
  RowChangeOut,
  RowRefOut,
  SubscriptionOut,
  TenantSummaryOut,
  UpdatesOut,
} from '../../lib/types';
import {
  appliedSentence,
  applyAction,
  attachmentAction,
  attachmentAddedSentence,
  attachmentRemovedSentence,
  type ConflictChoice,
  cleanSelection,
  cleanSentence,
  conflictsSettled,
  countsSentence,
  countUpdates,
  describeRow,
  detachAction,
  type FieldView,
  groupUpdates,
  NEVER_BY_ITSELF,
  NOT_COMPARED_NOTE,
  notAppliedSentence,
  PLAYERS_NOTE,
  ROW_KIND_LABEL,
  rowKey,
  todo,
} from '../../lib/updates';
import { renderClashCard } from './clash';

const required = requiredIn('Updates');

// How many rows of a group show before "Show more": a repository can change by the hundred.
const PAGE = 25;

type GroupId = 'conflicts' | 'changed' | 'added' | 'removed' | 'parents-added' | 'parents-removed';

type State = {
  library: TenantSummaryOut;
  subscription: SubscriptionOut;
  updates: UpdatesOut;
  // Rows put aside for now; they are offered again next time.
  skipped: Set<string>;
  // What was chosen about each conflict, by row and then by field.
  conflictChoices: Map<string, Map<string, ConflictChoice>>;
  // How a new row's name clash is settled, by row.
  clashChoices: Map<string, Map<string, Choice>>;
  shown: Map<GroupId, number>;
};

export type UpdatesView = {
  // Shows the updates of a repository the library has copied and can still be offered updates
  // from. Resolves to false when it cannot (not copied, not offered, not published), for the page
  // to show the repository instead.
  open(
    library: TenantSummaryOut,
    subscription: SubscriptionOut,
    isCurrent: () => boolean,
  ): Promise<boolean>;
  close(): void;
};

function listItem(text: string): HTMLElement {
  const item = document.createElement('li');

  item.textContent = text;

  return item;
}

// `view` is the updates block in the <RepositoriesPanel />, and `panel` the panel, whose templates
// it uses.
export function createUpdatesView(panel: HTMLElement, view: HTMLElement): UpdatesView {
  const title = required<HTMLElement>(view, '[data-updates-title]');
  const statusLine = required<HTMLElement>(view, '[data-updates-status]');
  const error = required<HTMLElement>(view, '[data-updates-error]');
  const gone = required<HTMLElement>(view, '[data-updates-gone]');
  const back = required<HTMLAnchorElement>(view, '[data-updates-back]');
  const body = required<HTMLElement>(view, '[data-updates-body]');
  const summary = required<HTMLElement>(view, '[data-updates-summary]');
  const notes = required<HTMLElement>(view, '[data-updates-notes]');
  const bulk = required<HTMLElement>(view, '[data-bulk]');
  const bulkSentence = required<HTMLElement>(view, '[data-bulk-sentence]');
  const bulkCheck = required<HTMLButtonElement>(view, '[data-bulk-check]');
  const bulkReceipt = required<HTMLElement>(view, '[data-bulk-receipt]');
  const bulkReceiptText = required<HTMLElement>(view, '[data-bulk-receipt-text]');
  const bulkCancel = required<HTMLButtonElement>(view, '[data-bulk-cancel]');
  const bulkApply = required<HTMLButtonElement>(view, '[data-bulk-apply]');
  const result = required<HTMLElement>(view, '[data-result]');
  const resultText = required<HTMLElement>(view, '[data-result-text]');
  const notApplied = required<HTMLElement>(view, '[data-not-applied]');
  const groups = required<HTMLElement>(view, '[data-groups]');
  const skippedSection = required<HTMLDetailsElement>(view, '[data-skipped-section]');
  const skippedTitle = required<HTMLElement>(view, '[data-skipped-title]');
  const skippedList = required<HTMLElement>(view, '[data-skipped]');
  const deletedSection = required<HTMLDetailsElement>(view, '[data-deleted-section]');
  const deletedTitle = required<HTMLElement>(view, '[data-deleted-title]');
  const deletedList = required<HTMLElement>(view, '[data-deleted]');

  let state: State | null = null;
  // Only the newest thing asked for paints, and a button pressed twice asks once.
  let latest = 0;
  let busy = false;

  function setBusy(value: boolean): void {
    busy = value;

    for (const button of view.querySelectorAll<HTMLButtonElement>('button')) {
      button.disabled = value || button.dataset.keepDisabled === 'true';
    }
  }

  // Keeps a button off for a reason that is not "busy", across the busy state.
  function keepDisabled(button: HTMLButtonElement, disabled: boolean): void {
    button.dataset.keepDisabled = String(disabled);
    button.disabled = busy || disabled;
  }

  // --- Doing something -------------------------------------------------------------------

  function showResult(outcome: ApplyUpdatesOut): void {
    resultText.textContent = appliedSentence(outcome);
    notApplied.replaceChildren(
      ...outcome.not_applied.map((entry) => listItem(notAppliedSentence(entry))),
    );
    notApplied.hidden = outcome.not_applied.length === 0;
    result.hidden = false;
  }

  // Applies, then reads the repository's updates again, since what is left is the repository's to
  // say. A refusal is shown at the row that asked.
  async function run(request: ApplyUpdatesRequest, rowStatus: HTMLElement): Promise<void> {
    const mine = state;

    if (!mine || busy) return;

    const turn = ++latest;

    setBusy(true);
    rowStatus.hidden = false;
    rowStatus.className = 'status-text';
    rowStatus.textContent = 'Applying…';

    try {
      const outcome = await applyUpdates(mine.library.id, mine.subscription.repository.id, request);
      const fresh = await getUpdates(mine.library.id, mine.subscription.repository.id, {
        fresh: true,
      });

      if (turn !== latest) return;

      showResult(outcome);
      mine.updates = fresh ?? emptyUpdates(mine.updates);
      bulkReceipt.hidden = true;
      bulkCheck.hidden = false;
      paint();
      result.scrollIntoView({ block: 'nearest' });
    } catch (cause) {
      if (turn !== latest) return;

      sayError(rowStatus, cause);
    } finally {
      if (turn === latest) setBusy(false);
    }
  }

  function emptyUpdates(from: UpdatesOut): UpdatesOut {
    return {
      ...from,
      changed: [],
      removed: [],
      deleted_locally: [],
      added: [],
      attachments_added: [],
      attachments_removed: [],
      attachments_deleted_locally: [],
    };
  }

  // --- Rows ------------------------------------------------------------------------------

  function skipButton(root: HTMLElement, key: string): void {
    required<HTMLButtonElement>(root, '[data-skip]').addEventListener('click', () => {
      state?.skipped.add(key);
      paint();
    });
  }

  function fieldBlock(
    mine: State,
    row: RowChangeOut,
    field: FieldView,
    index: number,
  ): HTMLElement {
    const block = cloneRoot(panel, '[data-field-template]');
    const values = required<HTMLElement>(block, '[data-values]');
    const note = required<HTMLElement>(block, '[data-note]');
    const conflict = required<HTMLElement>(block, '[data-conflict]');
    const key = rowKey(row);

    required<HTMLElement>(block, '[data-label]').textContent = field.label;

    const pair = (term: string, text: string) => {
      const dt = document.createElement('dt');
      const dd = document.createElement('dd');

      dt.textContent = term;
      dd.textContent = text;
      values.append(dt, dd);
    };

    if (field.added !== null || field.removed !== null) {
      if (field.added && field.added.length > 0) pair('Added', field.added.join(', '));
      if (field.removed && field.removed.length > 0) pair('Removed', field.removed.join(', '));
    } else {
      pair('Was', field.was ?? '(none)');
      pair('Now', field.now ?? '(none)');
      if (field.yours !== null) pair('Yours', field.yours);
    }

    note.textContent = field.note ?? '';
    note.hidden = field.note === null;

    if (field.state === 'conflict') {
      const keep = required<HTMLInputElement>(block, '[data-keep]');
      const take = required<HTMLInputElement>(block, '[data-take]');
      const choices = mine.conflictChoices.get(key) ?? new Map<string, ConflictChoice>();

      mine.conflictChoices.set(key, choices);
      keep.name = `conflict-${key}-${index}`;
      take.name = keep.name;
      keep.checked = choices.get(field.field) === 'keep';
      take.checked = choices.get(field.field) === 'take';
      conflict.hidden = false;
      conflict.addEventListener('change', () => {
        choices.set(field.field, keep.checked ? 'keep' : 'take');
        block.dispatchEvent(new CustomEvent('conflict-chosen', { bubbles: true }));
      });
    }

    return block;
  }

  function changeRow(mine: State, row: RowChangeOut): HTMLElement {
    const item = cloneRoot(panel, '[data-change-template]');
    const described = describeRow(row, mine.updates.names);
    const key = rowKey(row);
    const apply = required<HTMLButtonElement>(item, '[data-apply]');
    const chooseFirst = required<HTMLElement>(item, '[data-choose-first]');
    const status = required<HTMLElement>(item, '[data-status]');
    const choices = mine.conflictChoices.get(key) ?? new Map<string, ConflictChoice>();

    mine.conflictChoices.set(key, choices);
    required<HTMLElement>(item, '[data-kind]').textContent = described.kindLabel;
    required<HTMLElement>(item, '[data-name]').textContent = described.name;
    required<HTMLElement>(item, '[data-fields]').replaceChildren(
      ...described.fields.map((field, index) => fieldBlock(mine, row, field, index)),
    );

    function refresh(): void {
      const settled = conflictsSettled(described, choices);

      chooseFirst.hidden = settled;
      keepDisabled(apply, !settled || !described.appliable);
    }

    refresh();
    // A row whose only change cannot be applied has nothing to press.
    apply.hidden = !described.appliable;
    item.addEventListener('conflict-chosen', refresh);
    apply.addEventListener('click', () => {
      void run({ actions: [applyAction(row, choices)] }, status);
    });
    skipButton(item, key);

    return item;
  }

  function addedRow(mine: State, added: AddedOut): HTMLElement {
    const item = cloneRoot(panel, '[data-added-template]');
    const key = rowKey(added);
    const add = required<HTMLButtonElement>(item, '[data-add]');
    const status = required<HTMLElement>(item, '[data-status]');
    const choices = mine.clashChoices.get(key) ?? new Map<string, Choice>();

    mine.clashChoices.set(key, choices);
    required<HTMLElement>(item, '[data-kind]').textContent = ROW_KIND_LABEL[added.kind];
    required<HTMLElement>(item, '[data-name]').textContent = added.name;

    const { collision } = added;

    function refresh(): void {
      keepDisabled(
        add,
        collision !== null &&
          choiceProblem(collision, choices.get(collisionKey(collision))) !== null,
      );
    }

    if (collision) {
      required<HTMLElement>(item, '[data-clash]').append(
        renderClashCard(panel, collision, {
          index: key,
          repositoryName: mine.subscription.repository.name,
          choices,
          onChange: refresh,
        }),
      );
    }

    refresh();
    add.addEventListener('click', () => {
      const choice = collision ? choices.get(collisionKey(collision)) : undefined;

      void run(
        {
          actions: [
            {
              kind: added.kind,
              source_id: added.source_id,
              action: 'add',
              ...(choice
                ? {
                    resolution: {
                      action: choice.action,
                      ...(choice.action === 'rename' ? { name: choice.name.trim() } : {}),
                    },
                  }
                : {}),
            },
          ],
        },
        status,
      );
    });
    skipButton(item, key);

    return item;
  }

  function removedRow(ref: RowRefOut): HTMLElement {
    const item = cloneRoot(panel, '[data-removed-template]');
    const status = required<HTMLElement>(item, '[data-status]');

    required<HTMLElement>(item, '[data-kind]').textContent = ROW_KIND_LABEL[ref.kind];
    required<HTMLElement>(item, '[data-name]').textContent = ref.name;
    required<HTMLButtonElement>(item, '[data-detach]').addEventListener('click', () => {
      void run({ actions: [detachAction(ref)] }, status);
    });

    return item;
  }

  function parentRow(
    attachment: AttachmentRefOut | AttachmentAddedOut,
    adding: boolean,
  ): HTMLElement {
    const item = cloneRoot(panel, '[data-parent-template]');
    const status = required<HTMLElement>(item, '[data-status]');
    const add = required<HTMLButtonElement>(item, '[data-add]');
    const detach = required<HTMLButtonElement>(item, '[data-detach]');
    const reason = required<HTMLElement>(item, '[data-reason]');

    required<HTMLElement>(item, '[data-sentence]').textContent = adding
      ? attachmentAddedSentence(attachment)
      : attachmentRemovedSentence(attachment);

    if (adding) {
      const waiting = 'applicable' in attachment && !attachment.applicable;

      add.hidden = false;
      keepDisabled(add, waiting);
      reason.textContent =
        waiting && 'reason' in attachment && attachment.reason
          ? `It can be added once ${attachment.reason}.`
          : '';
      reason.hidden = !(waiting && reason.textContent);
      add.addEventListener('click', () => {
        void run({ actions: [], attachments: [attachmentAction(attachment, 'add')] }, status);
      });
    } else {
      detach.hidden = false;
      detach.addEventListener('click', () => {
        void run({ actions: [], attachments: [attachmentAction(attachment, 'detach')] }, status);
      });
    }

    return item;
  }

  // --- The page --------------------------------------------------------------------------

  function groupBlock(
    id: GroupId,
    label: string,
    hint: string | null,
    rows: HTMLElement[],
    total: number,
  ): HTMLElement {
    const mine = state as State;
    const block = cloneRoot(panel, '[data-group-template]');
    const more = required<HTMLButtonElement>(block, '[data-more]');
    const shown = mine.shown.get(id) ?? PAGE;

    required<HTMLElement>(block, '[data-title]').textContent = `${label} (${total})`;

    const hintLine = required<HTMLElement>(block, '[data-hint]');

    hintLine.textContent = hint ?? '';
    hintLine.hidden = hint === null;
    required<HTMLElement>(block, '[data-rows]').replaceChildren(...rows.slice(0, shown));
    more.hidden = rows.length <= shown;
    more.textContent = `Show more (${rows.length - shown} left)`;
    more.addEventListener('click', () => {
      mine.shown.set(id, shown + PAGE);
      paint();
    });

    return block;
  }

  function paint(): void {
    const mine = state;

    if (!mine) return;

    const { updates, skipped } = mine;
    const counts = countUpdates(updates);
    const all = groupUpdates(updates);
    const left = <T extends { kind: string; source_id: string }>(rows: T[]) =>
      rows.filter((row) => !skipped.has(rowKey(row)));

    summary.textContent =
      todo(counts) === 0
        ? 'Up to date: the repository has changed nothing your library has not taken.'
        : countsSentence(counts);
    notes.textContent = `${NOT_COMPARED_NOTE} ${NEVER_BY_ITSELF} ${PLAYERS_NOTE}`;

    const selection = cleanSelection(updates, skipped);

    bulk.hidden = selection.actions.length === 0;
    bulkSentence.textContent = cleanSentence(selection);

    const blocks: HTMLElement[] = [];
    const conflicts = left(all.conflicts);
    const changed = left(all.changed);
    const added = left(all.added);

    if (conflicts.length > 0) {
      blocks.push(
        groupBlock(
          'conflicts',
          'Conflicts',
          'Your library changed these too. Choose for each field whether to keep yours or take the update.',
          conflicts.map((row) => changeRow(mine, row)),
          conflicts.length,
        ),
      );
    }

    if (changed.length > 0) {
      blocks.push(
        groupBlock(
          'changed',
          'Changed',
          null,
          changed.map((row) => changeRow(mine, row)),
          changed.length,
        ),
      );
    }

    if (added.length > 0) {
      blocks.push(
        groupBlock(
          'added',
          'New',
          'The repository has these and your library does not.',
          added.map((row) => addedRow(mine, row)),
          added.length,
        ),
      );
    }

    if (all.removed.length > 0) {
      blocks.push(
        groupBlock(
          'removed',
          'Removed upstream',
          null,
          all.removed.map(removedRow),
          all.removed.length,
        ),
      );
    }

    if (all.attachmentsAdded.length > 0) {
      blocks.push(
        groupBlock(
          'parents-added',
          'Parents added by the repository',
          'It added a parent to entries your library holds copies of. Each is yours to decide.',
          all.attachmentsAdded.map((attachment) => parentRow(attachment, true)),
          all.attachmentsAdded.length,
        ),
      );
    }

    if (all.attachmentsRemoved.length > 0) {
      blocks.push(
        groupBlock(
          'parents-removed',
          'Parents the repository took off',
          'Detaching leaves the parent where it is.',
          all.attachmentsRemoved.map((attachment) => parentRow(attachment, false)),
          all.attachmentsRemoved.length,
        ),
      );
    }

    groups.replaceChildren(...blocks);

    // What was put aside, with a way back.
    const keys = new Map<string, string>();

    for (const row of [...updates.changed, ...updates.added]) keys.set(rowKey(row), row.name);

    const aside = [...skipped].filter((key) => keys.has(key));

    skippedSection.hidden = aside.length === 0;
    skippedTitle.textContent = `Skipped for now (${aside.length})`;
    skippedList.replaceChildren(
      ...aside.map((key) => {
        const item = cloneRoot(panel, '[data-skipped-template]');

        required<HTMLElement>(item, '[data-name]').textContent = keys.get(key) ?? '';
        required<HTMLButtonElement>(item, '[data-undo]').addEventListener('click', () => {
          skipped.delete(key);
          paint();
        });

        return item;
      }),
    );

    // What the library deleted itself: shown, nothing to do.
    const deleted = [
      ...all.deletedLocally.map((row) => row.name),
      ...all.attachmentsDeletedLocally.map(
        (attachment) => `${attachment.child_name}, inheriting from ${attachment.parent_name}`,
      ),
    ];

    deletedSection.hidden = deleted.length === 0;
    deletedTitle.textContent = `Deleted by your library (${deleted.length})`;
    deletedList.replaceChildren(
      ...deleted.map((name) => listItem(`${name}: you deleted it, so it is not compared.`)),
    );
  }

  // --- The buttons -----------------------------------------------------------------------

  // Apply all clean: checked first (made and rolled back), shown as a receipt, then made.
  bulkCheck.addEventListener('click', () => {
    const mine = state;

    if (!mine || busy) return;

    const selection = cleanSelection(mine.updates, mine.skipped);
    const turn = ++latest;

    setBusy(true);
    error.hidden = true;

    void (async () => {
      try {
        const outcome = await applyUpdates(mine.library.id, mine.subscription.repository.id, {
          actions: selection.actions,
          dry_run: true,
        });

        if (turn !== latest) return;

        bulkReceiptText.textContent = [
          appliedSentence(outcome),
          ...outcome.not_applied.map(notAppliedSentence),
        ].join(' ');
        bulkReceipt.hidden = false;
        bulkCheck.hidden = true;
      } catch (cause) {
        if (turn === latest) sayError(error, cause);
      } finally {
        if (turn === latest) setBusy(false);
      }
    })();
  });
  bulkCancel.addEventListener('click', () => {
    bulkReceipt.hidden = true;
    bulkCheck.hidden = false;
  });
  bulkApply.addEventListener('click', () => {
    const mine = state;

    if (!mine) return;

    void run({ actions: cleanSelection(mine.updates, mine.skipped).actions }, statusLine);
  });

  // --- Opening ---------------------------------------------------------------------------

  return {
    async open(library, subscription, isCurrent) {
      const copied = subscription.copied_at !== null;
      const offered =
        subscription.granted_at !== null && subscription.repository.published_at !== null;

      if (!copied || !offered) return false;

      const turn = ++latest;
      const { repository } = subscription;

      title.textContent = `Updates from ${repository.name}`;
      back.href = shelfHref(library.slug, repository.id);
      statusLine.textContent = 'Checking for updates…';
      error.hidden = true;
      gone.hidden = true;
      body.hidden = true;
      result.hidden = true;
      bulkReceipt.hidden = true;
      bulkCheck.hidden = false;
      setBusy(false);
      state = null;

      try {
        const updates = await getUpdates(library.id, repository.id, { fresh: true });

        if (turn !== latest || !isCurrent()) return true;

        if (updates === null) {
          statusLine.textContent = '';
          gone.textContent =
            'The repository cannot be checked right now: it is not offered to your library, or it is not published.';
          gone.hidden = false;

          return true;
        }

        state = {
          library,
          subscription,
          updates,
          skipped: new Set(),
          conflictChoices: new Map(),
          clashChoices: new Map(),
          shown: new Map(),
        };
        statusLine.textContent = 'Checked just now.';
        paint();
        body.hidden = false;
      } catch (cause) {
        if (turn !== latest || !isCurrent()) return true;

        statusLine.textContent = '';
        error.hidden = false;
        error.textContent = describeError(cause);
      }

      return true;
    },

    close() {
      latest += 1;
      state = null;
    },
  };
}
