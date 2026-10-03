// An entity's information (ADR 0112): every piece of it, rendered, with adding, editing and
// deleting (ADR 0101, 0109). The item page's Information section for GMs is the whole list;
// Notes (ADR 0113) are the same list narrowed to one type, with their own words.

import { type Renderer, showDescriptions } from '../../lib/descriptions';
import {
  createInformation,
  deleteInformation,
  type Information,
  type InformationDraft,
  listInformation,
  textOf,
  updateInformation,
} from '../../lib/information';
import { createStaleCache, RECENT_MS } from '../../lib/staleCache';
import { say } from '../../lib/statusLine';
import { cloneTemplate, requiredIn } from '../../lib/template';
import { renderInfoForm, saveError } from '../InfoForm/renderer';

// What a list shows and how it writes. The GM's whole Information section unless given.
export type InformationKind = {
  // Only information of these types.
  types?: string[];
  // Whether the viewer gets Add, Edit and Delete; the API still decides.
  canWrite: boolean;
  // What a new piece starts as.
  initial: InformationDraft;
  showType: boolean;
  addLabel: string;
  // Said when there's nothing to list.
  empty: string;
  visibilityLabel: string;
  visibilityNote?: string;
  // What a row says about itself: its type, who can read it.
  describe: (info: Information) => string;
  rowHeading: 'h3' | 'h4';
  // After a create or an edit is saved. If it throws after a create, the new piece is deleted.
  afterSave?: (
    saved: { id: string; isPublic: boolean },
    before: Information | null,
  ) => Promise<void>;
};

export type InformationOptions = {
  tenantId: string;
  renderer: Renderer;
  // After any save or delete.
  onChanged?: () => void;
};

export type RenderedInformation = {
  // Shows the information of `entityId`, replacing what was shown. Without `kind`, the GM's
  // whole Information section.
  load(entityId: string, kind?: Partial<InformationKind>): Promise<void>;
  // Fetches the information of `entityId` of those types ahead of `load`.
  prefetch(entityId: string, types?: string[]): void;
};

const INFORMATION: InformationKind = {
  canWrite: true,
  initial: { title: '', type: 'note', isPublic: false, content: '' },
  showType: true,
  addLabel: 'Add information',
  empty: '',
  visibilityLabel: 'Players can read this',
  describe: (info) => `${info.type} · ${info.is_public ? 'Players can read this' : 'Private'}`,
  rowHeading: 'h3',
};

const draftOf = (info: Information): InformationDraft => ({
  title: info.title,
  type: info.type,
  isPublic: info.is_public,
  content: textOf(info)?.content ?? '',
});

function needsTitle(draft: InformationDraft) {
  if (!draft.title) throw new Error('Give it a title.');
}

const required = requiredIn('Information');

const keyOf = (entityId: string, types?: string[]) => `${entityId}|${types?.join(',') ?? ''}`;

// `root` is whatever contains <Information />.
export function renderInformation(
  root: HTMLElement,
  options: InformationOptions,
): RenderedInformation {
  const { tenantId, renderer } = options;

  const list = required<HTMLUListElement>(root, '[data-list]');
  const empty = required<HTMLElement>(root, '[data-empty]');
  const addMount = required<HTMLElement>(root, '[data-add-mount]');
  const add = required<HTMLButtonElement>(root, '[data-add]');
  const status = required<HTMLElement>(root, '[data-status]');
  const rowTemplates = {
    h3: required<HTMLTemplateElement>(root, '[data-row-template-h3]'),
    h4: required<HTMLTemplateElement>(root, '[data-row-template-h4]'),
  };

  // The lists fetched so far, to show at once while they're fetched again.
  const lists = createStaleCache<Information[]>((key) => {
    const [entityId, types] = key.split('|');

    return listInformation(tenantId, entityId, types ? types.split(',') : undefined);
  });

  // What's shown now. A load replaces it, which retires whatever an earlier one still has
  // in flight.
  let session: { entityId: string; kind: InformationKind } | null = null;

  // What the list has drawn, so a fetch that found the same needn't redraw it.
  let painted: Information[] | null = null;

  // The status line and the form's mount only show while they have something in them.
  function setMount(form: HTMLElement | null) {
    addMount.replaceChildren(...(form ? [form] : []));
    addMount.hidden = !form;
  }

  const fail = (error: unknown) => say(status, saveError(error), true);

  const formOptions = (kind: InformationKind) => ({
    renderer,
    showType: kind.showType,
    showVisibility: true,
    visibilityLabel: kind.visibilityLabel,
    visibilityNote: kind.visibilityNote,
  });

  function paint(shown: NonNullable<typeof session>, infos: Information[]) {
    const rows = infos.map((info) => renderRow(shown, info));

    painted = infos;
    list.replaceChildren(...rows);
    list.hidden = rows.length === 0;
    empty.hidden = rows.length > 0 || !empty.textContent;
  }

  // `quiet`: something is drawn already, so redraw only if the answer differs, and say nothing
  // if the fetch fails.
  async function reload(shown: NonNullable<typeof session>, maxAge = 0, quiet = false) {
    try {
      const infos = await lists.refresh(keyOf(shown.entityId, shown.kind.types), maxAge);

      if (session !== shown) return;
      if (quiet && JSON.stringify(infos) === JSON.stringify(painted)) return;

      paint(shown, infos);
    } catch (error) {
      if (session === shown && !quiet) fail(error);
    }
  }

  async function afterWrite(shown: NonNullable<typeof session>) {
    say(status, '');
    await reload(shown);
    options.onChanged?.();
  }

  function renderRow(shown: NonNullable<typeof session>, info: Information): HTMLLIElement {
    const { kind } = shown;
    const row = cloneTemplate<HTMLLIElement>(rowTemplates[kind.rowHeading], 'li');
    const content = textOf(info)?.content;

    required<HTMLElement>(row, '[data-heading]').textContent = info.title || '(untitled)';
    required<HTMLElement>(row, '[data-describe]').textContent = kind.describe(info);

    if (content) {
      void showDescriptions(required<HTMLElement>(row, '[data-text]'), renderer, [
        { text: content },
      ]);
    }

    const actions = required<HTMLElement>(row, '[data-actions]');

    if (!kind.canWrite) {
      actions.remove();
      return row;
    }

    const remove = required<HTMLButtonElement>(row, '[data-delete]');

    required<HTMLButtonElement>(row, '[data-edit]').addEventListener('click', () => {
      let saved = false;

      row.replaceChildren(
        renderInfoForm(root, {
          ...formOptions(kind),
          initial: draftOf(info),
          onSubmit: async (draft) => {
            needsTitle(draft);
            await updateInformation(tenantId, info, draft);
            saved = true;
            await kind.afterSave?.({ id: info.id, isPublic: draft.isPublic }, info);
          },
          onClose: () => {
            if (saved) {
              void afterWrite(shown);
            } else if (painted) {
              paint(shown, painted);
            }
          },
        }),
      );
    });

    remove.addEventListener('click', async () => {
      if (!window.confirm(`Delete “${info.title}”? This can't be undone.`)) return;

      remove.disabled = true;

      try {
        await deleteInformation(tenantId, info);
        await afterWrite(shown);
      } catch (error) {
        remove.disabled = false;
        fail(error);
      }
    });

    return row;
  }

  add.addEventListener('click', () => {
    const shown = session;

    if (!shown) return;

    const { kind, entityId } = shown;
    let saved = false;

    add.hidden = true;
    setMount(
      renderInfoForm(root, {
        ...formOptions(kind),
        initial: kind.initial,
        onSubmit: async (draft) => {
          needsTitle(draft);

          const created = await createInformation(tenantId, entityId, draft);

          try {
            await kind.afterSave?.({ id: created.id, isPublic: draft.isPublic }, null);
          } catch (error) {
            // Kept, it could be something its author can't read.
            await deleteInformation(tenantId, created).catch(() => {});
            throw new Error(`It wasn't kept: ${saveError(error)}`);
          }

          saved = true;
        },
        onClose: () => {
          setMount(null);
          add.hidden = session !== shown || !kind.canWrite;

          if (saved) void afterWrite(shown);
        },
      }),
    );
  });

  return {
    async load(entityId, partial) {
      const kind: InformationKind = { ...INFORMATION, ...partial };
      const shown = { entityId, kind };

      session = shown;
      painted = null;
      list.replaceChildren();
      list.hidden = true;
      empty.textContent = kind.empty;
      empty.hidden = true;
      setMount(null);
      say(status, '');
      add.textContent = kind.addLabel;
      add.hidden = !kind.canWrite;

      const cached = lists.peek(keyOf(entityId, kind.types));

      if (cached) paint(shown, cached);

      await reload(shown, RECENT_MS, Boolean(cached));
    },

    prefetch: (entityId, types) => lists.prefetch(keyOf(entityId, types)),
  };
}
