import { fill, getAppLinks } from '@lorenzo/api-client';
import {
  type BundleReceipt,
  renderAudienceControl,
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
  errorNotice,
  field,
  message,
  relationshipHref,
  say,
  sectionHead,
  statusLine,
  submit,
} from './dom';

type Note = Schema<'InformationOut'>;

/** The address of a web in this app. */
const webHref = (tenant: string, id: string) => `/web/?${new URLSearchParams({ tenant, id })}`;

/** Where a note's link to an entry goes: here for what this app draws, else the app that does. */
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
  const registry = found.length ? await getAppLinks(API_BASE_URL).catch(() => null) : null;
  return render(doc, {
    locale: 'en-US',
    externalImages: false,
    resolve: {
      entity: (ref) => {
        const entry = found.find((e) => e.slug === ref.slug);
        if (!entry) return null;
        const title = entry.name;
        if (entry.kinds.includes('relationship'))
          return { href: relationshipHref(tenant, entry.entity_id), title };
        if (entry.kinds.includes('social_web'))
          return { href: webHref(tenant, entry.entity_id), title };
        const template = (
          [
            ['being', 'being_by_slug'],
            ['location', 'location_by_slug'],
            ['map', 'map_by_slug'],
            ['item', 'item_by_slug'],
            ['session', 'session_by_slug'],
            ['scene', 'scene_by_slug'],
            ['calendar', 'calendar_by_slug'],
          ] as const
        )
          .filter(([kind]) => entry.kinds.includes(kind))
          .map(([, name]) => registry?.links[name])
          .find(Boolean);
        const other = registry?.links.calendar_entry_by_slug;
        const link = template ?? other;
        return link && entry.slug
          ? { href: fill(link, { tenant, slug: entry.slug }), title }
          : null;
      },
    },
  });
}

/** The form that writes or changes one note; a new note starts restricted (see the audience after saving). */
function noteForm(tenant: string, entry: string, done: (saved: boolean) => void, original?: Note) {
  const form = el('form', '', 'stack');
  const title = field('Note title', original?.title ?? '');
  title.input.required = true;
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
      const created = createEditor({
        textarea: text,
        layout: 'tabs',
        toolbar: DEFAULT_TOOLBAR.filter((tool) => tool !== 'date'),
        render: (source) => renderText(tenant, source),
      });
      return {
        value: () => text.value,
        focus: () => text.focus(),
        destroy: () => created.destroy(),
      };
    },
  });
  const receipt: BundleReceipt = { id: original?.id ?? crypto.randomUUID() };
  const status = statusLine();
  const save = submit('Save note');
  form.append(
    title.label,
    el(
      'p',
      original
        ? 'The note keeps its own audience.'
        : 'A new note starts restricted. Choose who can read it after saving.',
      'status-text',
    ),
    editor.element,
    actions(
      save,
      button('Cancel', () => {
        editor.destroy();
        done(false);
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
            isPublic: original?.is_public ?? false,
            payloads: editor.read(),
            receipt,
          },
        });
        editor.destroy();
        done(true);
      } catch (error) {
        say(status, `${message(error)} Your draft is still here.`, true);
        save.disabled = false;
      }
    })();
  });
  return form;
}

/**
 * The notes of one entry (a relationship or a web): the ones the person may read, as cards, with
 * the way to add one and to change the ones they may. Each note keeps its own audience. The
 * section draws itself again after a save, so the page around it is left as it is.
 */
export function notes(tenant: string, entry: string): HTMLElement {
  const host = el('section', '', 'stack');
  host.setAttribute('aria-label', 'Notes');
  const draw = async () => {
    try {
      const [data, access] = await Promise.all([
        unwrap(
          await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
            params: { path: { tenant_id: tenant, entity_id: entry } },
            cache: 'no-cache',
          }),
        ),
        unwrap(
          await client.GET('/tenants/{tenant_id}/entities/{entity_id}/access', {
            params: { path: { tenant_id: tenant, entity_id: entry } },
            cache: 'no-store',
          }),
        ),
      ]);
      const redraw = () => void draw();
      const add = access.can_add_notes
        ? button(
            'Add note',
            () => {
              if (host.querySelector('form')) return;
              const frame = card();
              frame.body.append(
                noteForm(tenant, entry, (saved) => {
                  if (saved) redraw();
                  else frame.root.remove();
                }),
              );
              head.after(frame.root);
              frame.root.querySelector('input')?.focus();
            },
            { icon: 'add' },
          )
        : undefined;
      const head = sectionHead('Notes', {
        count: data.information.length,
        actions: add ? [add] : [],
      });
      const items: HTMLElement[] = [];
      for (const note of data.information) {
        // A note is an article of its own, so a reader of the page can move from one to the next.
        const article = el('article', '', 'card');
        const bodyOf = el('div', '', 'card-body stack-tight');
        article.append(bodyOf);
        const titleRow = el('div', '', 'row');
        titleRow.append(
          el('h3', note.title || 'Untitled note', 'item-title grow'),
          audienceBadge(
            note.is_public ? 'Everyone in this library' : 'Restricted',
            Boolean(note.is_public),
          ),
        );
        bodyOf.append(titleRow);
        if (note.created_by_name)
          bodyOf.append(el('p', `By ${note.created_by_name}`, 'status-text'));
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
        bodyOf.append(content);
        if (access.editable_information_ids.includes(note.id)) {
          bodyOf.append(
            actions(
              button(
                'Edit note',
                () => bodyOf.replaceChildren(noteForm(tenant, entry, () => redraw(), note)),
                { icon: 'edit' },
              ),
            ),
            renderAudienceControl({
              client,
              tenantId: tenant,
              informationId: note.id,
              onSaved: redraw,
            }),
          );
        }
        items.push(article);
      }
      host.replaceChildren(head, ...items);
      if (!data.information.length) host.append(empty('No notes are available to you here.'));
    } catch (error) {
      host.replaceChildren(sectionHead('Notes'), errorNotice(error));
    }
  };
  void draw();
  return host;
}
