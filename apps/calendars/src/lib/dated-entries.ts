import { rememberEntryAddress } from './addresses';
import { client, fetchAllPages, unwrap } from './api';
import { button, el, entryHref, field, link, message, select } from './dom';
import { creationVisibility } from './event-visibility';
import type { Definition, Period, Rule } from './types';
export async function attachDate(
  tenantId: string,
  entryId: string,
  periodId: string,
): Promise<void> {
  const path = { tenant_id: tenantId, entity_id: entryId };
  const result = await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
    params: { path },
  });
  await unwrap(result);
  const version = result.response.headers.get('etag');
  if (!version) throw new Error('Could not read the entry version.');
  const dates = await unwrap(
    await client.GET('/tenants/{tenant_id}/entities/{entity_id}/dates', { params: { path } }),
  );
  await unwrap(
    await client.PUT('/tenants/{tenant_id}/entities/{entity_id}/dates', {
      params: { path, header: { 'if-match': version } },
      body: { period_ids: [...new Set([...dates.map((d) => d.entity_id), periodId])] },
    }),
  );
}
export function createDatedEntry(tenantId: string, period: () => Promise<Period>): HTMLElement {
  const form = el('form', '', 'panel stack');
  const kind = select(
    'New entry',
    [
      ['event', 'Story event'],
      ['fact', 'Canonical fact'],
    ],
    'event',
  );
  const name = field('Entry name');
  name.input.required = true;
  const status = el('p');
  status.setAttribute('role', 'status');
  const save = el('button', 'Create dated entry', 'btn');
  save.type = 'submit';
  const id = crypto.randomUUID();
  const visibility = creationVisibility();
  kind.input.addEventListener('change', () => visibility.setEvent(kind.input.value === 'event'));
  let created = false;
  let target: Period | undefined;
  form.append(
    kind.label,
    name.label,
    visibility.label,
    el('p', 'Notes have their own audiences.', 'caption'),
    save,
    status,
  );
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    save.disabled = true;
    try {
      target ??= await period();
      if (!created) {
        try {
          await unwrap(
            await client.POST('/tenants/{tenant_id}/entities', {
              params: { path: { tenant_id: tenantId } },
              body: {
                id,
                name: name.input.value,
                kinds: [kind.input.value as 'event' | 'fact'],
                visibility: visibility.value(),
                parents: [],
              },
            }),
          );
        } catch (error) {
          const existing = await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
            params: { path: { tenant_id: tenantId, entity_id: id } },
          });
          if (!existing.data) throw error;
          if (!existing.data.kinds.includes(kind.input.value as 'event' | 'fact')) throw error;
        }
        created = true;
        kind.input.disabled = true;
        name.input.disabled = true;
      }
      await attachDate(tenantId, id, target.entity_id);
      if (form.isConnected) location.assign(`${entryHref(tenantId, id)}&add=information`);
    } catch (e) {
      status.textContent = message(e);
      if (created) {
        status.append(
          document.createTextNode(
            ' The entry was created; retry to finish associating its date, or ',
          ),
          link('open it', entryHref(tenantId, id)),
        );
      }
      save.disabled = false;
    }
  });
  return form;
}
export function recurrenceFields(definition: Definition, initial: Rule) {
  const host = el('div', '', 'form-grid');
  const segment = select(
    'Segment',
    definition.segments.map((s) => [s.key, s.name]),
    initial.segment,
  );
  const day = field('Day', String(initial.day), 'number');
  day.input.min = '1';
  day.input.max = '1000';
  const every = field('Every N years', String(initial.when.every), 'number');
  every.input.min = '1';
  every.input.max = '1000';
  const offset = field('Year offset', String(initial.when.offset), 'number');
  host.append(segment.label, day.label, every.label, offset.label);
  return {
    element: host,
    read: (): Rule => ({
      segment: segment.input.value,
      day: Number(day.input.value),
      when: { every: Number(every.input.value), offset: Number(offset.input.value) },
    }),
  };
}
export function createObservance(
  tenantId: string,
  calendarId: string,
  definition: Definition,
  initial: Rule,
): HTMLElement {
  const form = el('form', '', 'stack panel');
  const name = field('Observance name');
  name.input.required = true;
  const rules = recurrenceFields(definition, initial);
  const status = el('p');
  status.setAttribute('role', 'status');
  const save = el('button', 'Create recurring observance', 'btn');
  save.type = 'submit';
  const id = crypto.randomUUID();
  form.append(
    name.label,
    rules.element,
    el('p', 'Dates absent from a year are skipped. The observance starts restricted.', 'caption'),
    save,
    status,
  );
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    save.disabled = true;
    try {
      const entry = await unwrap(
        await client.POST('/tenants/{tenant_id}/calendars/{calendar_id}/observances', {
          params: { path: { tenant_id: tenantId, calendar_id: calendarId } },
          body: { id, name: name.input.value, rule: rules.read(), is_public: false },
        }),
      );
      if (form.isConnected) location.assign(entryHref(tenantId, entry.entity_id));
    } catch (e) {
      try {
        const existing = await client.GET('/tenants/{tenant_id}/observances/{entity_id}', {
          params: { path: { tenant_id: tenantId, entity_id: id } },
        });
        if (existing.data) {
          if (form.isConnected) location.assign(entryHref(tenantId, id));
          return;
        }
      } catch {
        /* Retain the draft when the result cannot be established. */
      }
      status.textContent = `${message(e)} Your draft is kept.`;
      save.disabled = false;
    }
  });
  return form;
}
export function attachExisting(tenantId: string, period: () => Promise<Period>): HTMLElement {
  const host = el('div', '', 'stack panel');
  const q = field('Find a fact or event');
  const results = el('div', '', 'stack-tight');
  const status = el('p');
  status.setAttribute('role', 'status');
  let request = 0;
  host.append(
    q.label,
    button(
      'Search entries',
      async () => {
        const turn = ++request;
        try {
          const page = await unwrap(
            await client.GET('/tenants/{tenant_id}/entities', {
              params: {
                path: { tenant_id: tenantId },
                query: { q: q.input.value, kind: ['fact', 'event'], size: 30 },
              },
            }),
          );
          if (turn !== request) return;
          results.replaceChildren();
          for (const entry of page.items)
            results.append(
              button(
                entry.name,
                async () => {
                  try {
                    const target = await period();
                    await attachDate(tenantId, entry.id, target.entity_id);
                    if (host.isConnected) location.assign(entryHref(tenantId, entry.id));
                  } catch (e) {
                    status.textContent = `${message(e)} Reload the entry before trying again.`;
                  }
                },
                true,
              ),
            );
          status.textContent = page.items.length
            ? 'Choose an entry to associate with this date.'
            : 'No matching entries are available to you.';
        } catch (e) {
          status.textContent = message(e);
        }
      },
      true,
    ),
    results,
    status,
  );
  return host;
}
export async function datedEntries(tenantId: string, periodId: string): Promise<HTMLElement> {
  const host = el('section', '', 'stack-tight');
  host.append(el('h3', 'Dated entries'));
  const entries = await fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/calendar-periods/{period_id}/entries', {
        params: { path: { tenant_id: tenantId, period_id: periodId }, query: { page, size: 100 } },
      }),
    ),
  );
  for (const entry of entries) {
    rememberEntryAddress(tenantId, entry);
    host.append(link(entry.name, entryHref(tenantId, entry.entity_id)));
  }
  if (!entries.length)
    host.append(el('p', 'No dated entries are available to you here.', 'caption'));
  return host;
}
