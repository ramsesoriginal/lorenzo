import { calendarDateLinks, getAppLinks } from '@lorenzo/api-client';
import {
  type BundleReceipt,
  renderAudienceControl,
  renderBundleEditor,
  renderInformationPayloads,
  saveInformationBundle,
} from '@lorenzo/information-editor';
import { parse, references, render } from '@lorenzo/lorenzoscript';
import { createEditor, DEFAULT_TOOLBAR } from '@lorenzo/lorenzoscript-editor';
import { rememberEntryAddress } from './addresses';
import { blobUrl, client, unwrap } from './api';
import { API_BASE_URL } from './config';
import { button, calendarHref, el, entryHref, feedback, field, icon, message, submit } from './dom';
import { informationLearning } from './learning';
import type { Entry, Information } from './types';

export async function renderText(tenantId: string, source: string): Promise<string> {
  const doc = parse(source);
  const slugs = references(doc).flatMap((r) => (r.kind === 'entity' ? [r.slug] : []));
  const found = slugs.length
    ? await unwrap(
        await client.GET('/tenants/{tenant_id}/entities/resolve', {
          params: { path: { tenant_id: tenantId }, query: { slug: [...new Set(slugs)] } },
        }),
      )
    : [];
  const expressions = references(doc).flatMap((r) => (r.kind === 'calendar' ? [r.expression] : []));
  const registry = expressions.length
    ? await getAppLinks(API_BASE_URL).catch(() => undefined)
    : undefined;
  const dates = await calendarDateLinks(
    client,
    registry,
    tenantId,
    references(doc).flatMap((r) => (r.kind === 'calendar' ? [r.expression] : [])),
  );
  for (const entry of found) rememberEntryAddress(tenantId, entry);
  return render(doc, {
    locale: 'en-US',
    externalImages: false,
    resolve: {
      calendar: (expression) => dates.get(expression) ?? null,
      entity: (ref) => {
        const match = found.find((e) => e.slug === ref.slug);
        return match
          ? {
              href: match.kinds.includes('calendar')
                ? calendarHref(tenantId, match.entity_id)
                : entryHref(tenantId, match.entity_id),
              title: match.name,
            }
          : null;
      },
    },
  });
}

const loadFile = (payload: { url: string; updated_at: string }) =>
  blobUrl(payload.url, payload.updated_at);

/** The form that writes or edits one note; the caller frames it. */
export function informationForm(
  tenantId: string,
  entryId: string,
  finished: () => void,
  original?: Information,
): HTMLElement {
  const form = el('form', '', 'stack');
  const title = field('Note title', original?.title ?? '');
  title.input.required = true;
  const status = feedback();
  const receipt: BundleReceipt = { id: original?.id ?? crypto.randomUUID() };
  const editor = renderBundleEditor({
    initial: original?.payloads,
    content: '',
    textLabel: 'Text',
    loadFile,
    createTextEditor(host, label, content) {
      const l = el('label', label, 'field-label');
      const textarea = el('textarea');
      textarea.value = content;
      textarea.id = `calendar-text-${crypto.randomUUID()}`;
      l.htmlFor = textarea.id;
      host.append(l, textarea);
      const editor = createEditor({
        textarea,
        layout: 'tabs',
        toolbar: DEFAULT_TOOLBAR.filter((tool) => tool !== 'date'),
        render: (source) => renderText(tenantId, source),
      });
      return {
        value: () => textarea.value,
        focus: () => textarea.focus(),
        destroy: () => editor.destroy(),
      };
    },
  });
  const save = submit('Save note');
  const actions = el('div', '', 'row');
  actions.append(
    save,
    button(
      'Cancel',
      () => {
        editor.destroy();
        (form.closest('[data-form-frame]') ?? form).remove();
      },
      true,
    ),
  );
  form.append(
    title.label,
    el(
      'p',
      original
        ? 'The note keeps its own audience.'
        : 'A new note starts restricted. Choose who can read it after saving.',
      'caption',
    ),
    editor.element,
    actions,
    status.node,
  );
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    save.disabled = true;
    status.busy('Saving…');
    try {
      await editor.ready();
      await saveInformationBundle({
        client,
        tenantId,
        entityId: entryId,
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
      finished();
    } catch (e) {
      status.fail(`${message(e)} Your draft is still here.`);
      save.disabled = false;
    }
  });
  return form;
}

/**
 * An entry's notes. On a page of its own they are cards under a heading with the way to add one;
 * `compact`, inside a panel, they are plain blocks under a smaller heading.
 */
export function informationView(
  tenantId: string,
  entry: Entry,
  canWrite: boolean,
  refresh: () => void,
  canRecordLearning = false,
  access?: { can_add_notes: boolean; editable_information_ids: string[] },
  compact = false,
): HTMLElement {
  const host = el('section', '', compact ? 'stack-tight' : 'stack');
  const canAdd = access?.can_add_notes ?? canWrite;
  const head = el('div', '', 'section-head');
  head.append(el(compact ? 'h3' : 'h2', 'Notes'));
  host.append(head);
  const notes = [...entry.information].sort((a, b) => a.order - b.order);
  for (const info of notes) {
    const card = el('article', '', compact ? 'note stack-tight' : 'card');
    const body = compact ? card : el('div', '', 'card-body stack-tight');
    if (!compact) card.append(body);
    const heading = el('div', '', 'note-head');
    heading.append(el('h3', info.title || 'Untitled note'));
    if (!info.is_public) {
      const badge = el('span', '', 'badge-visibility');
      badge.append(icon('private'), document.createTextNode('Restricted'));
      heading.append(badge);
    }
    body.append(heading);
    if (info.created_by_name) body.append(el('p', `By ${info.created_by_name}`, 'caption'));
    const content = el('div');
    renderInformationPayloads(content, {
      information: info,
      loadFile,
      renderText: async (host, source) => {
        try {
          host.innerHTML = await renderText(tenantId, source);
        } catch {
          host.textContent = source;
        }
      },
    });
    body.append(content);
    if (canRecordLearning) body.append(informationLearning(tenantId, info.id));
    if (access ? access.editable_information_ids.includes(info.id) : canWrite) {
      const tools = el('div', '', 'row');
      tools.append(
        button(
          'Edit note',
          () => {
            body.replaceChildren(informationForm(tenantId, entry.id, refresh, info));
          },
          true,
          'edit',
        ),
      );
      body.append(
        tools,
        renderAudienceControl({
          client,
          tenantId,
          informationId: info.id,
          allowParticipants: entry.kinds.includes('event'),
        }),
      );
    }
    host.append(card);
  }
  if (!notes.length) host.append(el('p', 'No notes are available to you here.', 'lede'));
  if (canAdd)
    head.append(
      button(
        'Add note',
        () => {
          const existing = host.querySelector('form');
          if (existing) {
            existing.querySelector('input')?.focus();
            return;
          }
          const frame = el('div', '', 'card card-body');
          frame.dataset.formFrame = '';
          frame.append(informationForm(tenantId, entry.id, refresh));
          host.append(frame);
        },
        true,
        'add',
      ),
    );
  return host;
}
