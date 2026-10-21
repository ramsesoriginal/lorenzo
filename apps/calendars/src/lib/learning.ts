import { client, unwrap } from './api';
import { button, el, entryHref, link, message, select } from './dom';
import { entryPicker } from './entry-picker';

type Filter = { event_id?: string; being_id?: string; information_id?: string };

/** Staff only: callers must pass the freshly resolved Event capability. */
export async function learningList(tenantId: string, filter: Filter): Promise<HTMLElement> {
  const host = el('div', '', 'stack-tight');
  let page = 1;
  const status = el('p');
  status.setAttribute('role', 'status');
  const list = el('ul', '', 'stack-tight');
  const more = button('More learning records', () => load(page + 1), true);
  let busy = false;
  async function load(next: number) {
    if (busy) return;
    busy = true;
    try {
      const rows = await unwrap(
        await client.GET('/tenants/{tenant_id}/event-learning', {
          params: { path: { tenant_id: tenantId }, query: { ...filter, size: 30, page: next } },
        }),
      );
      for (const row of rows.items) {
        const item = el('li');
        item.append(
          link(row.being_name, entryHref(tenantId, row.being_entity_id)),
          document.createTextNode(' learned '),
          link(
            row.information_title || 'Untitled information',
            entryHref(tenantId, row.information_entity_id),
          ),
          document.createTextNode(` (${row.information_entity_name}) at `),
          link(row.event_name, entryHref(tenantId, row.event_entity_id)),
        );
        list.append(item);
      }
      page = next;
      more.hidden = next >= (rows.pages ?? 0);
      status.textContent = rows.total ? '' : 'No learning history is recorded here.';
    } catch (error) {
      status.textContent = message(error);
    } finally {
      busy = false;
    }
  }
  host.append(list, more, status);
  await load(1);
  return host;
}

export function informationLearning(tenantId: string, informationId: string): HTMLElement {
  const host = el('details');
  host.append(el('summary', 'Recorded learning'));
  let loaded = false;
  host.addEventListener('toggle', async () => {
    if (!host.open || loaded) return;
    loaded = true;
    host.append(await learningList(tenantId, { information_id: informationId }));
  });
  return host;
}

export async function eventLearning(tenantId: string, eventId: string): Promise<HTMLElement> {
  const path = { tenant_id: tenantId, event_id: eventId };
  const host = el('details', '', 'panel');
  host.dataset.learning = '';
  const body = el('div', '', 'stack');
  host.append(el('summary', 'Learning'), body);
  const status = el('p');
  status.setAttribute('role', 'status');
  const list = el('div', '', 'stack-tight');
  const participant = select('Who learned?', [['', 'Choose a participant']], '');
  const information = select('Information learned', [['', 'Choose an entry first']], '');
  let version = '';
  let busy = false;
  let selection = 0;
  async function run(action: () => Promise<void>) {
    if (busy || !host.isConnected) return;
    busy = true;
    status.textContent = 'Saving…';
    try {
      await action();
    } catch (error) {
      status.textContent = `${message(error)} Your selection is kept. Refresh saved learning before retrying a conflicting edit.`;
    } finally {
      busy = false;
    }
  }
  let page = 1;
  const more = button('More Event learning', () => run(() => load(page + 1)), true);
  async function load(next = 1) {
    if (next === 1) {
      const revision = await client.GET('/tenants/{tenant_id}/events/{event_id}/learning-version', {
        params: { path },
      });
      await unwrap(revision);
      version = revision.response.headers.get('etag') ?? '';
      const people = await unwrap(
        await client.GET('/tenants/{tenant_id}/events/{event_id}/participants', {
          params: { path },
        }),
      );
      const selected = participant.input.value;
      participant.input.replaceChildren(new Option('Choose a participant', ''));
      for (const person of people)
        participant.input.add(new Option(person.name, person.being_entity_id));
      participant.input.value = selected;
    }
    const rows = await unwrap(
      await client.GET('/tenants/{tenant_id}/event-learning', {
        params: {
          path: { tenant_id: tenantId },
          query: { event_id: eventId, page: next, size: 30 },
        },
      }),
    );
    if (next === 1) list.replaceChildren();
    for (const row of rows.items) {
      const item = el('div', '', 'stack-tight');
      item.append(
        el(
          'p',
          `${row.being_name} learned ${row.information_title || 'Untitled information'} (${row.information_entity_name}).`,
        ),
        link('Read Information', entryHref(tenantId, row.information_entity_id)),
        link(`Learning recorded for ${row.being_name}`, entryHref(tenantId, row.being_entity_id)),
        button(
          'Remove learning record',
          () =>
            run(async () => {
              await unwrap(
                await client.DELETE(
                  '/tenants/{tenant_id}/events/{event_id}/learning/{being_id}/{information_id}',
                  {
                    params: {
                      path: {
                        ...path,
                        being_id: row.being_entity_id,
                        information_id: row.information_id,
                      },
                      header: { 'if-match': version },
                    },
                  },
                ),
              );
              await load();
              status.textContent = 'Learning record removed. Audiences are unchanged.';
            }),
          true,
        ),
      );
      list.append(item);
    }
    page = next;
    more.hidden = next >= (rows.pages ?? 0);
    if (!rows.total)
      list.append(el('p', 'No learning history is recorded for this Event.', 'caption'));
  }
  body.append(
    el(
      'p',
      'Record what a participating being learned here. Audiences stay unchanged. The link follows the Information, including later edits to its wording.',
      'caption',
    ),
    list,
    more,
    button(
      'Refresh saved learning',
      () =>
        run(async () => {
          await load();
          status.textContent = 'Saved learning refreshed.';
        }),
      true,
    ),
    participant.label,
    entryPicker(tenantId, 'Find an entry with Information', undefined, (entry) => {
      const turn = ++selection;
      information.input.replaceChildren(new Option('Loading Information…', ''));
      void (async () => {
        try {
          const detail = await unwrap(
            await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
              params: { path: { tenant_id: tenantId, entity_id: entry.id } },
            }),
          );
          if (turn !== selection || !host.isConnected) return;
          information.input.replaceChildren(new Option('Choose Information', ''));
          for (const info of detail.information)
            information.input.add(
              new Option(`${entry.name}: ${info.title || 'Untitled information'}`, info.id),
            );
          status.textContent = detail.information.length
            ? 'Choose the Information learned.'
            : 'This entry has no available Information.';
        } catch (error) {
          if (turn === selection) status.textContent = message(error);
        }
      })();
    }),
    information.label,
    button(
      'Record learning',
      () =>
        run(async () => {
          if (!participant.input.value || !information.input.value)
            throw new Error('Choose a participant and Information first.');
          await unwrap(
            await client.PUT(
              '/tenants/{tenant_id}/events/{event_id}/learning/{being_id}/{information_id}',
              {
                params: {
                  path: {
                    ...path,
                    being_id: participant.input.value,
                    information_id: information.input.value,
                  },
                  header: { 'if-match': version },
                },
              },
            ),
          );
          await load();
          status.textContent = 'Learning recorded. Audiences are unchanged.';
        }),
      true,
    ),
    status,
  );
  await load();
  return host;
}
