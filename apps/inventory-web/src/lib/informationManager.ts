// The item page's Information section for GMs (ADR 0112): every piece of the
// entity's information, rendered, with adding, editing, and deleting it
// (ADR 0101, 0109). Notes (ADR 0113) are the same list narrowed to one type,
// with their own words: see notes.ts.
import { type Renderer, showDescriptions } from './descriptions';
import { infoForm, saveError } from './infoForm';
import {
  createInformation,
  deleteInformation,
  type Information,
  type InformationDraft,
  listInformation,
  textOf,
  updateInformation,
} from './information';

/** What a list shows and how it writes. The GM's whole Information section unless given. */
export type ManagerKind = {
  /** Only information of these types. */
  types?: string[];
  /** Whether the viewer gets Add, Edit and Delete; the API still decides. */
  canWrite: boolean;
  /** What a new piece starts as. */
  initial: InformationDraft;
  showType: boolean;
  addLabel: string;
  /** Said when there's nothing to list. */
  empty: string;
  visibilityLabel: string;
  visibilityNote?: string;
  /** What a row says about itself: its type, who can read it. */
  describe: (info: Information) => string;
  rowHeading: 'h3' | 'h4';
  /** After a create or an edit is saved. If it throws after a create, the new piece is deleted. */
  afterSave?: (
    saved: { id: string; isPublic: boolean },
    before: Information | null,
  ) => Promise<void>;
};

const INFORMATION: ManagerKind = {
  canWrite: true,
  initial: { title: '', type: 'note', isPublic: false, content: '' },
  showType: true,
  addLabel: 'Add information',
  empty: '',
  visibilityLabel: 'Players can read this',
  describe: (info) => `${info.type} · ${info.is_public ? 'Players can read this' : 'Private'}`,
  rowHeading: 'h3',
};

const make = <K extends keyof HTMLElementTagNameMap>(tag: K, className: string, text = '') =>
  Object.assign(document.createElement(tag), { className, textContent: text });

const button = (label: string, className = 'btn btn-secondary') =>
  Object.assign(make('button', className, label), { type: 'button' });

const draftOf = (info: Information): InformationDraft => ({
  title: info.title,
  type: info.type,
  isPublic: info.is_public,
  content: textOf(info)?.content ?? '',
});

const needsTitle = (draft: InformationDraft) => {
  if (!draft.title) throw new Error('Give it a title.');
};

/** Renders the section into `container`. `onChanged` runs after any save or delete. */
export async function renderInformationManager(
  container: HTMLElement,
  options: {
    tenantId: string;
    entityId: string;
    renderer: Renderer;
    onChanged: () => void;
    kind?: Partial<ManagerKind>;
  },
): Promise<void> {
  const { tenantId, entityId, renderer } = options;
  const kind: ManagerKind = { ...INFORMATION, ...options.kind };
  const list = make('ul', 'information-list');
  const empty = Object.assign(make('p', 'status-text', kind.empty), { hidden: true });
  const status = make('p', 'status-text');
  status.setAttribute('role', 'status');
  const add = button(kind.addLabel);
  add.hidden = !kind.canWrite;
  const addMount = make('div', '');
  container.replaceChildren(list, empty, addMount, add, status);

  const formOptions = {
    renderer,
    showType: kind.showType,
    showVisibility: true,
    visibilityLabel: kind.visibilityLabel,
    visibilityNote: kind.visibilityNote,
  };
  const fail = (e: unknown) => {
    status.classList.add('error-text');
    status.textContent = saveError(e);
  };
  const reload = async () => {
    try {
      const rows = (await listInformation(tenantId, entityId, kind.types)).map(row);
      list.replaceChildren(...rows);
      empty.hidden = rows.length > 0 || !kind.empty;
    } catch (e) {
      fail(e);
    }
  };
  const afterWrite = async () => {
    status.textContent = '';
    status.classList.remove('error-text');
    await reload();
    options.onChanged();
  };

  function row(info: Information): HTMLLIElement {
    const li = make('li', 'information-row');
    const text = make('div', 'item-detail-descriptions');
    li.append(
      make(kind.rowHeading, '', info.title || '(untitled)'),
      make('p', 'status-text', kind.describe(info)),
      text,
    );
    const content = textOf(info)?.content;
    if (content) void showDescriptions(text, renderer, [{ text: content }]);
    if (!kind.canWrite) return li;

    const edit = button('Edit');
    const remove = button('Delete', 'btn-danger');
    const actions = make('div', 'field-row');
    actions.append(edit, remove);
    li.append(actions);
    edit.addEventListener('click', () => {
      let saved = false;
      li.replaceChildren(
        infoForm({
          ...formOptions,
          initial: draftOf(info),
          onSubmit: async (draft) => {
            needsTitle(draft);
            await updateInformation(tenantId, info, draft);
            saved = true;
            await kind.afterSave?.({ id: info.id, isPublic: draft.isPublic }, info);
          },
          onClose: () => void (saved ? afterWrite() : reload()),
        }),
      );
    });
    remove.addEventListener('click', async () => {
      if (!window.confirm(`Delete “${info.title}”? This can't be undone.`)) return;
      remove.disabled = true;
      try {
        await deleteInformation(tenantId, info);
        await afterWrite();
      } catch (e) {
        remove.disabled = false;
        fail(e);
      }
    });
    return li;
  }

  add.addEventListener('click', () => {
    add.hidden = true;
    let saved = false;
    addMount.replaceChildren(
      infoForm({
        ...formOptions,
        initial: kind.initial,
        onSubmit: async (draft) => {
          needsTitle(draft);
          const created = await createInformation(tenantId, entityId, draft);
          try {
            await kind.afterSave?.({ id: created.id, isPublic: draft.isPublic }, null);
          } catch (e) {
            // Kept, it could be something its author can't read.
            await deleteInformation(tenantId, created).catch(() => {});
            throw new Error(`It wasn't kept: ${saveError(e)}`);
          }
          saved = true;
        },
        onClose: () => {
          addMount.replaceChildren();
          add.hidden = false;
          if (saved) void afterWrite();
        },
      }),
    );
  });

  await reload();
}
