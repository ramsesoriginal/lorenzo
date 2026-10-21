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
import { button, el, field, message, select } from './dom';

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
            : registry.links.calendar_entry_by_slug;
        return template
          ? { href: fill(template, { tenant, slug: entry.slug }), title: entry.name }
          : null;
      },
    },
  });
}
function noteForm(tenant: string, entry: string, refresh: () => void, original?: Note) {
  const form = el('form', '', 'panel stack');
  const title = field('Note title', original?.title ?? '');
  title.input.required = true;
  const audience = select(
    'Who can read this',
    [
      ['restricted', 'Me and Session GMs'],
      ['shared', 'Session participants'],
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
      const caption = el('label', label);
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
  const status = el('p');
  status.setAttribute('role', 'status');
  const save = el('button', 'Save note', 'btn');
  save.type = 'submit';
  form.append(
    title.label,
    audience.label,
    editor.element,
    save,
    button('Cancel', () => {
      editor.destroy();
      form.remove();
    }),
    status,
  );
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    save.disabled = true;
    status.textContent = 'Saving…';
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
        status.textContent = `${message(error)} Your draft is still here.`;
        save.disabled = false;
      }
    })();
  });
  return form;
}
export async function notes(tenant: string, entry: string, refresh: () => void) {
  const [data, access] = await Promise.all([
    unwrap(
      await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
        params: { path: { tenant_id: tenant, entity_id: entry } },
        cache: 'no-store',
      }),
    ),
    unwrap(
      await client.GET('/tenants/{tenant_id}/entities/{entity_id}/access', {
        params: { path: { tenant_id: tenant, entity_id: entry } },
        cache: 'no-store',
      }),
    ),
  ]);
  const host = el('section', '', 'stack');
  host.append(el('h3', 'Notes'));
  for (const note of data.information) {
    const card = el('article', '', 'panel stack-tight');
    card.append(
      el('h4', note.title),
      el(
        'p',
        `${note.created_by_name ? `By ${note.created_by_name} · ` : ''}${note.is_public ? 'Session participants' : 'Author and Session GMs'}`,
        'caption',
      ),
    );
    const content = el('div');
    renderInformationPayloads(content, {
      information: note,
      loadFile,
      renderText: async (target, source) => {
        try {
          target.innerHTML = await renderText(tenant, source);
        } catch {
          target.textContent = source;
        }
      },
    });
    card.append(content);
    if (access.editable_information_ids.includes(note.id))
      card.append(
        button('Edit note', () => {
          card.replaceChildren(noteForm(tenant, entry, refresh, note));
        }),
      );
    host.append(card);
  }
  if (!data.information.length)
    host.append(el('p', 'No notes are available to you here.', 'caption'));
  if (access.can_add_notes)
    host.append(
      button('Add note', () => {
        if (!host.querySelector('form')) host.append(noteForm(tenant, entry, refresh));
      }),
    );
  return host;
}
