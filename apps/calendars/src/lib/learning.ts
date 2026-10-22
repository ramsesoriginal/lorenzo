import { client, unwrap } from './api';
import { button, disclosure, el, entryHref, feedback, link, message, select } from './dom';
import { entryPicker } from './entry-picker';

type Filter = { event_id?: string; being_id?: string; information_id?: string };

/** Staff only: callers must pass the freshly resolved Event capability. */
export async function learningList(tenantId: string, filter: Filter): Promise<HTMLElement> {
  const host = el('div', '', 'stack-tight');
  let page = 1;
  const status = feedback();
  const list = el('ul', '', 'list');
  const empty = el('p', 'No learning history is recorded here.', 'lede');
  empty.hidden = true;
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
        const sentence = el('span');
        sentence.append(
          link(row.being_name, entryHref(tenantId, row.being_entity_id)),
          document.createTextNode(' learned '),
          link(
            row.information_title || 'Untitled note',
            entryHref(tenantId, row.information_entity_id),
          ),
          document.createTextNode(` (${row.information_entity_name}) at `),
          link(row.event_name, entryHref(tenantId, row.event_entity_id)),
        );
        item.append(sentence);
        list.append(item);
      }
      page = next;
      more.hidden = next >= (rows.pages ?? 0);
      empty.hidden = Boolean(rows.total);
      list.hidden = !rows.total;
    } catch (error) {
      status.fail(message(error));
    } finally {
      busy = false;
    }
  }
  host.append(list, empty, more, status.node);
  await load(1);
  return host;
}

export function informationLearning(tenantId: string, informationId: string): HTMLElement {
  const host = disclosure('Recorded learning');
  let loaded = false;
  host.root.addEventListener('toggle', async () => {
    if (!host.root.open || loaded) return;
    loaded = true;
    host.body.append(await learningList(tenantId, { information_id: informationId }));
  });
  return host.root;
}

export async function eventLearning(tenantId: string, eventId: string): Promise<HTMLElement> {
  const path = { tenant_id: tenantId, event_id: eventId };
  const panel = disclosure('Learning', true);
  const host = panel.root;
  host.dataset.learning = '';
  const status = feedback();
  const list = el('ul', '', 'list');
  const empty = el('p', 'No learning history is recorded for this Event.', 'lede');
  const participant = select('Who learned?', [['', 'Choose a participant']], '');
  const information = select('Note learned', [['', 'Choose an entry first']], '');
  let version = '';
  let busy = false;
  let selection = 0;
  async function run(action: () => Promise<void>) {
    if (busy || !host.isConnected) return;
    busy = true;
    status.busy('Saving…');
    try {
      await action();
    } catch (error) {
      status.fail(
        `${message(error)} Your selection is kept. Refresh saved learning before retrying a conflicting edit.`,
      );
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
      const item = el('li', '', 'row');
      const sentence = el(
        'p',
        `${row.being_name} learned ${row.information_title || 'Untitled note'} (${row.information_entity_name}).`,
        'grow',
      );
      item.append(
        sentence,
        link('Read the note', entryHref(tenantId, row.information_entity_id)),
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
              status.say('Learning record removed. Audiences are unchanged.');
            }),
          true,
          'close',
        ),
      );
      list.append(item);
    }
    page = next;
    more.hidden = next >= (rows.pages ?? 0);
    list.hidden = !list.childElementCount;
    empty.hidden = Boolean(list.childElementCount);
  }
  const actions = el('div', '', 'row');
  actions.append(
    button(
      'Record learning',
      () =>
        run(async () => {
          if (!participant.input.value || !information.input.value)
            throw new Error('Choose a participant and a note first.');
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
          status.say('Learning recorded. Audiences are unchanged.');
        }),
      false,
      'add',
    ),
    button(
      'Refresh saved learning',
      () =>
        run(async () => {
          await load();
          status.say('Saved learning refreshed.');
        }),
      true,
      'refresh',
    ),
  );
  panel.body.append(
    el(
      'p',
      'Record what a participating being learned here. Audiences stay unchanged. The link follows the note, including later edits to its wording.',
      'caption',
    ),
    list,
    empty,
    more,
    participant.label,
    entryPicker(tenantId, 'Find an entry with notes', undefined, (entry) => {
      const turn = ++selection;
      information.input.replaceChildren(new Option('Loading notes…', ''));
      void (async () => {
        try {
          const detail = await unwrap(
            await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
              params: { path: { tenant_id: tenantId, entity_id: entry.id } },
            }),
          );
          if (turn !== selection || !host.isConnected) return;
          information.input.replaceChildren(new Option('Choose a note', ''));
          for (const info of detail.information)
            information.input.add(
              new Option(`${entry.name}: ${info.title || 'Untitled note'}`, info.id),
            );
          status.say(
            detail.information.length
              ? 'Choose the note learned.'
              : 'This entry has no notes available to you.',
          );
        } catch (error) {
          if (turn === selection) status.fail(message(error));
        }
      })();
    }),
    information.label,
    actions,
    status.node,
  );
  await load();
  return host;
}
