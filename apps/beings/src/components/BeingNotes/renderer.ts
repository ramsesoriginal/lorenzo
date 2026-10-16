import { renderAudienceControl } from '@lorenzo/information-editor';
import { client } from '../../lib/api';
// Notes on a being (ADR 0271), the way inventory-web has them on items (ADR 0113) but with the four
// audiences (GM only, Everyone, Some characters, Player note) and an order the writer sets (ADR
// 0237). Anyone who can see a note reads it; whoever may write, adds, edits, reorders and deletes.
// The API remains the gate for every write.

import { listBeings } from '../../lib/beingList';
import { at, type Renderer, showDescriptions } from '../../lib/descriptions';
import { errorMessage } from '../../lib/errorMessage';
import type { GmWords } from '../../lib/gmTitle';
import {
  createInformation,
  deleteInformation,
  type Information,
  type InformationDraft,
  listInformation,
  textOf,
  updateInformation,
} from '../../lib/information';
import {
  type Audience,
  applyKnowers,
  audienceLabel,
  audienceOf,
  EVERYONE_NOTE_IN_REPOSITORY,
  type Knower,
  knownCharacters,
  listKnowers,
  moved,
  planAudience,
  reordered,
  saveOrder,
  showsLock,
  visibleOrder,
} from '../../lib/notes';
import { say } from '../../lib/statusLine';
import { cloneTemplate, requiredIn } from '../../lib/template';
import { type AudienceFieldOptions, renderAudienceField } from '../AudienceField/renderer';
import { renderInfoForm, saveError } from '../InfoForm/renderer';

export type BeingNotesOptions = {
  tenantId: string;
  renderer: Renderer;
  beingId: string;
  // What the being's campaigns call their game master, or "GM" (ADR 0294).
  words: GmWords;
  // Whether the being is an entry of a repository: a note that is Everyone's goes with every copy of
  // it, so it shows a lock, and `Make GM only` to take it back (RFC 0038 section 5, ADR 0293).
  inRepository?: boolean;
  // After any save, reorder or delete.
  onChanged?: () => void;
};

export type NotesViewer = {
  // Whether the viewer gets Add, Edit, Delete and reordering; the API still decides.
  canWrite: boolean;
  // A GM or a member of the library may tell some characters; a player writes a Player note.
  runsTheTable: boolean;
};

export type RenderedBeingNotes = {
  load(viewer: NotesViewer): Promise<void>;
};

const required = requiredIn('Being notes');

type Row = { info: Information; knowers: Knower[] | null };

// `root` is the <BeingNotes /> block.
export function renderBeingNotes(
  root: HTMLElement,
  options: BeingNotesOptions,
): RenderedBeingNotes {
  const { tenantId, beingId } = options;
  const list = required<HTMLUListElement>(root, '[data-list]');
  const empty = required<HTMLElement>(root, '[data-empty]');
  const addMount = required<HTMLElement>(root, '[data-add-mount]');
  const add = required<HTMLButtonElement>(root, '[data-add]');
  const status = required<HTMLElement>(root, '[data-status]');
  const rowTemplate = required<HTMLTemplateElement>(root, '[data-note-template]');

  let viewer: NotesViewer = { canWrite: false, runsTheTable: false };
  // Each time a load starts, an earlier one still in flight is retired.
  let turn = 0;
  let rows: Row[] = [];

  const fail = (error: unknown) => say(status, saveError(error), true);

  function offer(): Audience[] {
    return viewer.runsTheTable ? ['gm', 'everyone', 'some', 'player'] : ['player', 'everyone'];
  }

  function fieldOptions(initial: Audience, told: readonly string[]): AudienceFieldOptions {
    const allowed = offer();

    return {
      words: options.words,
      offer: allowed,
      initial: allowed.includes(initial) ? initial : (allowed[0] as Audience),
      told,
      candidates: async () =>
        (await listBeings(tenantId)).map((being) => ({
          entity_id: being.entity_id,
          name: being.name,
        })),
    };
  }

  async function reload() {
    const mine = ++turn;

    try {
      const infos = await listInformation(tenantId, beingId, ['note']);
      // Who each is told to: asked only of those who may write, and refused to everyone else.
      const all = await Promise.all(
        infos.map(async (info) => ({
          info,
          knowers: viewer.canWrite && !info.is_public ? await listKnowers(tenantId, info.id) : null,
        })),
      );

      if (mine !== turn) return;

      rows = all;
      paint();
    } catch (error) {
      if (mine === turn) fail(error);
    }
  }

  function paint() {
    list.replaceChildren(...rows.map((row, index) => drawRow(row, index)));
    list.hidden = rows.length === 0;
    empty.hidden = rows.length > 0;
  }

  async function afterWrite() {
    say(status, '');
    await reload();
    options.onChanged?.();
  }

  async function move(index: number, to: number) {
    const ids = rows.map((row) => row.info.id);
    const wanted = moved(ids, index, to);

    if (wanted.every((id, i) => id === ids[i])) return;

    say(status, 'Moving…');

    try {
      // The order is of everything the viewer can see, not only notes: the others keep their places.
      await saveOrder(tenantId, beingId, reordered(await visibleOrder(tenantId, beingId), wanted));
      await afterWrite();
    } catch (error) {
      fail(error);
    }
  }

  // One edit of the row (its `is_public`), not a rewrite of the note: its text, title and order stay.
  async function makeGmOnly(info: Information, button: HTMLButtonElement) {
    button.disabled = true;
    say(status, '');

    try {
      await updateInformation(tenantId, info, { ...draftOf(info), isPublic: false });
      await afterWrite();
    } catch (error) {
      button.disabled = false;
      fail(error);
    }
  }

  function drawRow(row: Row, index: number): HTMLLIElement {
    const { info, knowers } = row;
    const item = cloneTemplate<HTMLLIElement>(rowTemplate, 'li');
    const content = textOf(info)?.content;

    required<HTMLElement>(item, '[data-heading]').textContent = info.title || 'Note';
    required<HTMLElement>(item, '[data-audience]').textContent = audienceLabel(
      audienceOf(info, knowers, beingId),
      options.words,
    );

    if (content) {
      void showDescriptions(required<HTMLElement>(item, '[data-text]'), options.renderer, [
        { text: content, home: beingId },
      ]);
    }

    // Who wrote it: shown exactly when the note is (ADR 0277).
    const author = required<HTMLElement>(item, '[data-author]');

    author.hidden = !info.created_by_name;
    author.textContent = info.created_by_name ?? '';

    // Everyone's text in a repository: said, with one click to take it back for whoever may write.
    const lock = required<HTMLElement>(item, '[data-lock]');
    const makeGm = required<HTMLButtonElement>(lock, '[data-make-gm]');

    required<HTMLElement>(lock, '[data-lock-text]').textContent = EVERYONE_NOTE_IN_REPOSITORY;
    lock.hidden = !showsLock(options.inRepository, info);
    makeGm.hidden = !viewer.canWrite;
    makeGm.setAttribute('aria-label', `Make GM only: ${info.title || 'Note'}`);
    makeGm.addEventListener('click', () => void makeGmOnly(info, makeGm));

    const actions = required<HTMLElement>(item, '[data-actions]');

    if (!viewer.canWrite) {
      actions.remove();
      return item;
    }

    actions.append(
      renderAudienceControl({ client, tenantId, informationId: info.id, onSaved: afterWrite }),
    );

    const up = required<HTMLButtonElement>(item, '[data-up]');
    const down = required<HTMLButtonElement>(item, '[data-down]');
    const remove = required<HTMLButtonElement>(item, '[data-delete]');

    up.disabled = index === 0;
    down.disabled = index === rows.length - 1;
    up.addEventListener('click', () => void move(index, index - 1));
    down.addEventListener('click', () => void move(index, index + 1));

    required<HTMLButtonElement>(item, '[data-edit]').addEventListener('click', () => {
      let saved = false;
      // The audience can only be changed by someone who can list who was told.
      const current = audienceOf(info, knowers, beingId);
      const field =
        current === 'shared'
          ? null
          : renderAudienceField(
              root,
              fieldOptions(current, knowers ? knownCharacters(knowers) : []),
            );

      item.replaceChildren(
        renderInfoForm(root, {
          renderer: at(options.renderer, beingId),
          initial: draftOf(info),
          titleLabel: 'Label',
          textLabel: 'Note',
          showVisibility: false,
          ...(field && { extra: field.element }),
          onSubmit: async (draft) => {
            const plan = field
              ? planAudience(field.value(), knowers ?? [], beingId, options.words)
              : { isPublic: info.is_public, add: [], remove: [], removePlayers: [] };

            await updateInformation(tenantId, info, {
              ...draft,
              title: draft.title || 'Note',
              type: 'note',
              isPublic: info.is_public,
            });
            saved = true;

            try {
              await applyKnowers(tenantId, info.id, plan);
            } catch (error) {
              throw new Error(
                `The note was saved, but who can read it wasn't changed: ${errorMessage(error)}`,
              );
            }
          },
          onClose: () => {
            if (saved) void afterWrite();
            else paint();
          },
        }),
      );
    });

    remove.addEventListener('click', async () => {
      if (!window.confirm(`Delete “${info.title || 'Note'}”? This can't be undone.`)) return;

      remove.disabled = true;

      try {
        await deleteInformation(tenantId, info);
        await afterWrite();
      } catch (error) {
        remove.disabled = false;
        fail(error);
      }
    });

    return item;
  }

  const draftOf = (info: Information): InformationDraft => ({
    title: info.title,
    type: 'note',
    isPublic: info.is_public,
    content: textOf(info)?.content ?? '',
  });

  add.addEventListener('click', () => {
    let saved = false;

    // Private by default (ADR 0113): the GMs' own, or a player's note for their being.
    const field = renderAudienceField(
      root,
      fieldOptions(viewer.runsTheTable ? 'gm' : 'player', []),
    );

    add.hidden = true;
    addMount.hidden = false;
    addMount.replaceChildren(
      renderInfoForm(root, {
        renderer: at(options.renderer, beingId),
        initial: { title: 'Note', type: 'note', isPublic: false, content: '' },
        titleLabel: 'Label',
        textLabel: 'Note',
        showVisibility: false,
        extra: field.element,
        onSubmit: async (draft) => {
          const plan = planAudience(field.value(), [], beingId, options.words);
          const created = await createInformation(tenantId, beingId, {
            ...draft,
            title: draft.title || 'Note',
            type: 'note',
            isPublic: false,
          });

          try {
            await applyKnowers(tenantId, created.id, plan);
          } catch (error) {
            // Kept, it could be something its author can't read.
            await deleteInformation(tenantId, created).catch(() => {});
            throw new Error(`It wasn't kept: ${saveError(error)}`);
          }

          saved = true;
        },
        onClose: () => {
          addMount.replaceChildren();
          addMount.hidden = true;
          add.hidden = !viewer.canWrite;

          if (saved) void afterWrite();
        },
      }),
    );
  });

  return {
    async load(next) {
      viewer = next;
      rows = [];
      list.replaceChildren();
      list.hidden = true;
      empty.hidden = true;
      addMount.replaceChildren();
      addMount.hidden = true;
      add.hidden = !next.canWrite;
      say(status, '');
      await reload();
    },
  };
}
