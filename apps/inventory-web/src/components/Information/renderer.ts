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

function required<T extends Element>(root: ParentNode, selector: string): T {
  const element = root.querySelector<T>(selector);

  if (!element) {
    throw new Error(`Information is missing ${selector}.`);
  }

  return element;
}

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

  // What's shown now. A load replaces it, which retires whatever an earlier one still has
  // in flight.
  let session: { entityId: string; kind: InformationKind } | null = null;

  // The status line and the form's mount only show while they have something in them.
  function setStatus(message: string, failed = false) {
    status.textContent = message;
    status.classList.toggle('error-text', failed);
    status.hidden = !message;
  }

  function setMount(form: HTMLElement | null) {
    addMount.replaceChildren(...(form ? [form] : []));
    addMount.hidden = !form;
  }

  const fail = (error: unknown) => setStatus(saveError(error), true);

  const formOptions = (kind: InformationKind) => ({
    renderer,
    showType: kind.showType,
    showVisibility: true,
    visibilityLabel: kind.visibilityLabel,
    visibilityNote: kind.visibilityNote,
  });

  async function reload(shown: NonNullable<typeof session>) {
    try {
      const rows = (await listInformation(tenantId, shown.entityId, shown.kind.types)).map((info) =>
        renderRow(shown, info),
      );

      if (session !== shown) return;

      list.replaceChildren(...rows);
      list.hidden = rows.length === 0;
      empty.hidden = rows.length > 0 || !empty.textContent;
    } catch (error) {
      if (session === shown) fail(error);
    }
  }

  async function afterWrite(shown: NonNullable<typeof session>) {
    setStatus('');
    await reload(shown);
    options.onChanged?.();
  }

  function renderRow(shown: NonNullable<typeof session>, info: Information): HTMLLIElement {
    const { kind } = shown;
    const row = required<HTMLLIElement>(
      rowTemplates[kind.rowHeading].content.cloneNode(true) as DocumentFragment,
      'li',
    );
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
          onClose: () => void (saved ? afterWrite(shown) : reload(shown)),
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
      list.replaceChildren();
      list.hidden = true;
      empty.textContent = kind.empty;
      empty.hidden = true;
      setMount(null);
      setStatus('');
      add.textContent = kind.addLabel;
      add.hidden = !kind.canWrite;

      await reload(shown);
    },
  };
}
