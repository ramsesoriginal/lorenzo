import { client, unwrap } from './api';
import { button, disclosure, el, entryHref, feedback, link, message } from './dom';
import { entryPicker } from './entry-picker';
import { groupFromParticipants } from './event-groups';

export async function participants(
  tenantId: string,
  eventId: string,
  canCreateGroup = false,
): Promise<HTMLElement> {
  const path = { tenant_id: tenantId, event_id: eventId };
  const panel = disclosure('Participating beings', true);
  const host = panel.root;
  const body = panel.body;
  host.dataset.participants = '';
  const list = el('ul', '', 'list');
  const empty = el('p', 'No beings are recorded as taking part yet.', 'lede');
  const status = feedback();
  let version = '';
  let busy = false;
  async function run(action: () => Promise<void>) {
    if (busy) return;
    busy = true;
    status.busy('Saving…');
    try {
      await action();
    } catch (error) {
      status.fail(
        `${message(error)} Your selection is kept. Refresh saved participants before retrying a conflicting edit.`,
      );
    } finally {
      busy = false;
    }
  }
  type Rows = Awaited<ReturnType<typeof read>>;
  function draw(rows: Rows) {
    list.replaceChildren();
    list.hidden = !rows.length;
    empty.hidden = rows.length > 0;
    for (const being of rows) {
      const row = el('li', '', 'row');
      const name = link(being.name, entryHref(tenantId, being.being_entity_id));
      name.classList.add('grow');
      row.append(
        name,
        button(
          'Remove participant',
          () =>
            run(async () => {
              const result = await client.DELETE(
                '/tenants/{tenant_id}/events/{event_id}/participants/{being_id}',
                {
                  params: {
                    path: { ...path, being_id: being.being_entity_id },
                    header: { 'if-match': version },
                  },
                },
              );
              draw(await unwrap(result));
              version = result.response.headers.get('etag') ?? '';
              status.say('Participation removed.');
            }),
          true,
          'close',
        ),
      );
      list.append(row);
    }
  }
  async function read() {
    const result = await client.GET('/tenants/{tenant_id}/events/{event_id}/participants', {
      params: { path },
      cache: 'no-store',
    });
    const rows = await unwrap(result);
    version = result.response.headers.get('etag') ?? '';
    return rows;
  }
  let selected: { id: string; name: string } | undefined;
  const selection = el('p', 'Choose a being to add.', 'caption');
  draw(await read());
  const actions = el('div', '', 'row');
  actions.append(
    button(
      'Add participant',
      () =>
        run(async () => {
          if (!selected) throw new Error('Choose a being first.');
          if (!version) throw new Error('Refresh saved participants first.');
          const result = await client.PUT(
            '/tenants/{tenant_id}/events/{event_id}/participants/{being_id}',
            {
              params: { path: { ...path, being_id: selected.id }, header: { 'if-match': version } },
            },
          );
          draw(await unwrap(result));
          version = result.response.headers.get('etag') ?? '';
          status.say('Participation recorded.');
        }),
      false,
      'add',
    ),
    button(
      'Refresh saved participants',
      () =>
        run(async () => {
          draw(await read());
          status.say('Saved participants refreshed.');
        }),
      true,
      'refresh',
    ),
  );
  body.append(
    el(
      'p',
      'Participation records who took part. Participant sharing is chosen separately for the Event and its notes; learning is recorded separately.',
      'caption',
    ),
    list,
    empty,
    entryPicker(tenantId, 'Find a participating being', 'being', (entry) => {
      selected = entry;
      selection.textContent = `Selected being: ${entry.name}`;
    }),
    selection,
    actions,
    status.node,
  );
  if (canCreateGroup) body.append(groupFromParticipants(tenantId, eventId));
  return host;
}
