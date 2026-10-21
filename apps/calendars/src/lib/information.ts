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
import { button, calendarHref, el, entryHref, field, message } from './dom';
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
export function informationForm(
  tenantId: string,
  entryId: string,
  finished: () => void,
  original?: Information,
): HTMLElement {
  const form = el('form', '', 'stack panel');
  const title = field('Information title', original?.title ?? '');
  title.input.required = true;
  const status = el('p');
  status.setAttribute('role', 'status');
  const receipt: BundleReceipt = { id: original?.id ?? crypto.randomUUID() };
  const editor = renderBundleEditor({
    initial: original?.payloads,
    content: '',
    textLabel: 'Text',
    loadFile,
    createTextEditor(host, label, content) {
      const l = el('label', label);
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
  const save = el('button', 'Save information', 'btn');
  save.type = 'submit';
  const actions = el('div', '', 'row');
  actions.append(
    save,
    button(
      'Cancel',
      () => {
        editor.destroy();
        form.remove();
      },
      true,
    ),
  );
  form.append(
    title.label,
    el(
      'p',
      original
        ? 'The information keeps its own audience.'
        : 'New information starts restricted. Choose who can read it after saving.',
      'caption',
    ),
    editor.element,
    actions,
    status,
  );
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    save.disabled = true;
    status.textContent = 'Saving…';
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
      status.textContent = `${message(e)} Your draft is still here.`;
      save.disabled = false;
    }
  });
  return form;
}
export function informationView(
  tenantId: string,
  entry: Entry,
  canWrite: boolean,
  refresh: () => void,
  canRecordLearning = false,
  access?: { can_add_notes: boolean; editable_information_ids: string[] },
): HTMLElement {
  const host = el('section', '', 'stack');
  host.append(el('h2', 'Information'));
  for (const info of [...entry.information].sort((a, b) => a.order - b.order)) {
    const card = el('article', '', 'panel stack-tight');
    card.append(el('h3', info.title || 'Untitled information'));
    if (info.created_by_name) card.append(el('p', `By ${info.created_by_name}`, 'caption'));
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
    card.append(content);
    if (canRecordLearning) card.append(informationLearning(tenantId, info.id));
    if (access ? access.editable_information_ids.includes(info.id) : canWrite) {
      card.append(
        button(
          'Edit information',
          () => {
            card.replaceChildren(informationForm(tenantId, entry.id, refresh, info));
          },
          true,
        ),
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
  if (!entry.information.length)
    host.append(el('p', 'No information is available to you here.', 'caption'));
  if (access?.can_add_notes ?? canWrite)
    host.append(
      button(
        'Add information',
        () => {
          const existing = host.querySelector('form');
          if (existing) {
            existing.querySelector('input')?.focus();
            return;
          }
          host.append(informationForm(tenantId, entry.id, refresh));
        },
        true,
      ),
    );
  return host;
}
