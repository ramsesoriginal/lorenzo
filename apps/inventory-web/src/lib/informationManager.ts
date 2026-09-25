// The item page's Information section for GMs (ADR 0112): every piece of the
// entity's information, rendered, with adding, editing, and deleting it
// (ADR 0101, 0109).
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
  options: { tenantId: string; entityId: string; renderer: Renderer; onChanged: () => void },
): Promise<void> {
  const { tenantId, entityId, renderer } = options;
  const list = make('ul', 'information-list');
  const status = make('p', 'status-text');
  status.setAttribute('role', 'status');
  const add = button('Add information');
  const addMount = make('div', '');
  container.replaceChildren(list, addMount, add, status);

  const fail = (e: unknown) => {
    status.classList.add('error-text');
    status.textContent = saveError(e);
  };
  const reload = async () => {
    try {
      list.replaceChildren(...(await listInformation(tenantId, entityId)).map(row));
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
    const visibility = info.is_public ? 'Players can read this' : 'Private';
    const text = make('div', 'item-detail-descriptions');
    const edit = button('Edit');
    const remove = button('Delete', 'btn-danger');
    const actions = make('div', 'field-row');
    actions.append(edit, remove);
    li.append(
      make('h3', '', info.title || '(untitled)'),
      make('p', 'status-text', `${info.type} · ${visibility}`),
      text,
      actions,
    );
    const content = textOf(info)?.content;
    if (content) void showDescriptions(text, renderer, [{ text: content }]);

    edit.addEventListener('click', () => {
      let saved = false;
      li.replaceChildren(
        infoForm({
          initial: draftOf(info),
          renderer,
          showType: true,
          showVisibility: true,
          onSubmit: async (draft) => {
            needsTitle(draft);
            await updateInformation(tenantId, info, draft);
            saved = true;
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
        initial: { title: '', type: 'note', isPublic: false, content: '' },
        renderer,
        showType: true,
        showVisibility: true,
        onSubmit: async (draft) => {
          needsTitle(draft);
          await createInformation(tenantId, entityId, draft);
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
