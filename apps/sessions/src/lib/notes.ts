import { fill, getAppLinks } from '@lorenzo/api-client';
import {
  type BundleReceipt,
  renderBundleEditor,
  renderInformationPayloads,
  saveInformationBundle,
} from '@lorenzo/information-editor';
import { parse, references, render } from '@lorenzo/lorenzoscript';
import { createEditor, DEFAULT_TOOLBAR } from '@lorenzo/lorenzoscript-editor';
import { client, loadFile, type Schema, unwrap } from './api';
import { API_BASE_URL } from './config';
import {
  actions,
  audienceBadge,
  button,
  card,
  el,
  empty,
  field,
  message,
  say,
  sectionHead,
  select,
  statusLine,
  submit,
} from './dom';

type Note = Schema<'InformationOut'>;
async function renderText(tenant: string, source: string) {
  const doc = parse(source);
  const slugs = [...new Set(references(doc).flatMap((r) => (r.kind === 'entity' ? [r.slug] : [])))];
  const found = slugs.length
    ? await unwrap(
        await client.GET('/tenants/{tenant_id}/entities/resolve', {
          params: { path: { tenant_id: tenant }, query: { slug: slugs } },
        }),
      )
    : [];
  const registry = await getAppLinks(API_BASE_URL);
  return render(doc, {
    locale: 'en-US',
    externalImages: false,
    resolve: {
      entity: (ref) => {
        const entry = found.find((e) => e.slug === ref.slug);
        if (!entry) return null;
        const template = entry.kinds.includes('session')
          ? registry.links.session_by_slug
          : entry.kinds.includes('being')
            ? registry.links.being_by_slug
            : entry.kinds.includes('scene')
              ? registry.links.scene_by_slug
              : registry.links.calendar_entry_by_slug;
        return template
          ? { href: fill(template, { tenant, slug: entry.slug }), title: entry.name }
          : null;
      },
    },
  });
}
function noteForm(
  tenant: string,
  entry: string,
  refresh: () => void,
  cancel: () => void,
  original?: Note,
  scope: 'session' | 'scene' = 'session',
) {
  const form = el('form', '', 'stack');
  const title = field('Note title', original?.title ?? '');
  title.input.required = true;
  const audience = select(
    'Who can read this',
    [
      ['restricted', scope === 'session' ? 'Me and Session GMs' : 'Me and entry managers'],
      ['shared', scope === 'session' ? 'Session participants' : 'Everyone in this library'],
    ],
    original?.is_public ? 'shared' : 'restricted',
  );
  const editor = renderBundleEditor({
    initial: original?.payloads,
    content: '',
    textLabel: 'Note',
    loadFile,
    createTextEditor(host, label, content) {
      const text = el('textarea');
      text.id = `note-${crypto.randomUUID()}`;
      text.value = content;
      const caption = el('label', label, 'field-label');
      caption.htmlFor = text.id;
      host.append(caption, text);
      const editor = createEditor({
        textarea: text,
        layout: 'tabs',
        toolbar: DEFAULT_TOOLBAR.filter((t) => t !== 'date'),
        render: (source) => renderText(tenant, source),
      });
      return {
        value: () => text.value,
        focus: () => text.focus(),
        destroy: () => editor.destroy(),
      };
    },
  });
  const receipt: BundleReceipt = { id: original?.id ?? crypto.randomUUID() };
  const status = statusLine();
  const save = submit('Save note');
  form.append(
    title.label,
    audience.label,
    editor.element,
    actions(
      save,
      button('Cancel', () => {
        editor.destroy();
        cancel();
      }),
    ),
    status,
  );
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    save.disabled = true;
    say(status, 'Saving…');
    void (async () => {
      try {
        await editor.ready();
        await saveInformationBundle({
          client,
          tenantId: tenant,
          entityId: entry,
          original,
          draft: {
            title: title.input.value,
            type: original?.type ?? 'note',
            isPublic: audience.input.value === 'shared',
            payloads: editor.read(),
            receipt,
          },
        });
        editor.destroy();
        refresh();
      } catch (error) {
        say(status, `${message(error)} Your draft is still here.`, true);
        save.disabled = false;
      }
    })();
  });
  return form;
}
/** `level` is 2 for the page's own Notes section and 4 for the group inside a Scene's card. */
export async function notes(
  tenant: string,
  entry: string,
  refresh: () => void,
  scope: 'session' | 'scene' = 'session',
  level: 2 | 4 = 2,
) {
  const [data, access] = await Promise.all([
    unwrap(
      await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
        params: { path: { tenant_id: tenant, entity_id: entry } },
      }),
    ),
    unwrap(
      await client.GET('/tenants/{tenant_id}/entities/{entity_id}/access', {
        params: { path: { tenant_id: tenant, entity_id: entry } },
        cache: 'no-store',
      }),
    ),
  ]);
  const host = el('div', '', 'stack');
  const add = access.can_add_notes
    ? button(
        'Add note',
        () => {
          if (host.querySelector('form')) return;
          const wrapper = card(
            noteForm(tenant, entry, refresh, () => wrapper.root.remove(), undefined, scope),
          );
          head.after(wrapper.root);
        },
        { icon: 'add' },
      )
    : undefined;
  const head =
    level === 2
      ? sectionHead('Notes', { count: data.information.length, actions: add ? [add] : [] })
      : el('div', '', 'row');
  if (level === 4) {
    head.append(el('h4', 'Notes', 'group-title grow'));
    if (add) head.append(add);
  }
  host.append(head);
  for (const note of data.information) {
    const article = el('article', '', 'card');
    const body = el('div', '', 'card-body stack-tight');
    article.append(body);
    const shared = note.is_public;
    const audience =
      scope === 'session'
        ? shared
          ? 'Session participants'
          : 'Author and Session GMs'
        : shared
          ? 'Everyone in this library'
          : 'Author and entry managers';
    const titleRow = el('div', '', 'row');
    titleRow.append(
      el(level === 2 ? 'h3' : 'h5', note.title, 'item-title grow'),
      audienceBadge(audience, shared),
    );
    body.append(titleRow);
    if (note.created_by_name) body.append(el('p', `By ${note.created_by_name}`, 'status-text'));
    const content = el('div');
    renderInformationPayloads(content, {
      information: note,
      loadFile,
      renderText: async (target, source) => {
        try {
          target.classList.add('ls-content');
          target.innerHTML = await renderText(tenant, source);
        } catch {
          target.textContent = source;
        }
      },
    });
    body.append(content);
    if (access.editable_information_ids.includes(note.id))
      body.append(
        button('Edit note', () => {
          const previous = [...article.childNodes];
          article.replaceChildren(
            noteForm(
              tenant,
              entry,
              refresh,
              () => article.replaceChildren(...previous),
              note,
              scope,
            ),
          );
          article.firstElementChild?.classList.add('card-body');
        }),
      );
    host.append(article);
  }
  if (!data.information.length) host.append(empty('No notes are available to you here.'));
  return host;
}
