import { fill, getAppLinks } from '@lorenzo/api-client';
import { client, type components, LorenzoApiError, unwrap } from './api';
import { API_BASE_URL } from './config';
import { button, disclosure, el, entryHref, feedback, field, link, message, select } from './dom';

type Relationship = components['schemas']['RelationshipOut'];

/** Reader graph with separately gated staff editing; the API remains authoritative. */
export async function eventOrder(
  tenantId: string,
  eventId: string,
  canEdit = false,
): Promise<HTMLElement | null> {
  const registry = await getAppLinks(API_BASE_URL).catch(() => null);
  const path = { tenant_id: tenantId, event_id: eventId };
  const panel = disclosure('Order and causes', true);
  const host = panel.root;
  host.dataset.eventOrder = '';
  const body = panel.body;
  const assertions = el('ul', '', 'list');
  const none = el('p', '', 'lede');
  const status = feedback();
  let version = '';
  let busy = false;
  const query = field('Find an Event');
  const results = el('div', '', 'row');
  const selected = el('p', 'Choose an Event to relate or compare.', 'caption');
  let target: { id: string; name: string } | undefined;
  const relationship = select(
    'Relationship',
    [
      ['before', 'Happened before'],
      ['after', 'Happened after'],
      ['causes', 'Caused'],
      ['caused-by', 'Was caused by'],
    ],
    'before',
  );
  relationship.input.setAttribute('aria-label', 'Relationship');
  const comparison = el('div', '', 'stack-tight');
  async function run(action: () => Promise<void>) {
    if (busy || !host.isConnected) return;
    busy = true;
    status.clear();
    try {
      await action();
    } catch (error) {
      status.fail(
        canEdit
          ? `${message(error)} Your selection is kept. Refresh the saved relationships before retrying a conflicting edit.`
          : message(error),
      );
    } finally {
      busy = false;
    }
  }
  function render(rows: Relationship[]) {
    assertions.replaceChildren();
    assertions.hidden = !rows.length;
    none.hidden = rows.length > 0;
    none.textContent = canEdit
      ? 'No ordering relationships are recorded yet.'
      : 'No shared relationships are available in your view.';
    for (const row of rows) {
      const incoming = row.to_event_id === eventId;
      const otherId = incoming ? row.from_event_id : row.to_event_id;
      const otherName = incoming ? row.from_name : row.to_name;
      const label =
        row.kind === 'causes'
          ? incoming
            ? 'Was caused by'
            : 'Caused'
          : incoming
            ? 'Happened after'
            : 'Happened before';
      const line = el('li', '', 'row');
      line.append(el('span', label, 'relation'), link(otherName, entryHref(tenantId, otherId)));
      if (row.evidence === 'lived') {
        line.append(
          el('span', `Lived order · ${row.being_name ?? 'participating being'}`, 'caption'),
        );
        const template = registry?.links.lived_order;
        if (template && row.being_entity_id)
          line.append(
            link(
              'Review lived evidence',
              fill(template, { tenant: tenantId, id: row.being_entity_id }),
            ),
          );
        assertions.append(line);
        continue;
      }
      if (canEdit) {
        const spacer = el('span', '', 'grow');
        line.append(
          el(
            'span',
            row.is_shared ? 'Shared with readers of both Events' : 'Private relationship',
            'caption',
          ),
          spacer,
          button(
            row.is_shared ? 'Make relationship private' : 'Share relationship',
            () =>
              run(async () => {
                const result = await client.PUT(
                  '/tenants/{tenant_id}/events/{event_id}/relationships/{other_event_id}/sharing',
                  {
                    params: {
                      path: { ...path, other_event_id: otherId },
                      header: { 'if-match': version },
                    },
                    body: {
                      kind: row.kind,
                      direction: incoming ? 'incoming' : 'outgoing',
                      is_shared: !row.is_shared,
                    },
                  },
                );
                render(await unwrap(result));
                version = result.response.headers.get('etag') ?? '';
                comparison.replaceChildren();
                status.say(
                  row.is_shared
                    ? 'Relationship is private.'
                    : 'Relationship shared. Readers still need access to both Events.',
                );
              }),
            true,
          ),
          button(
            'Remove',
            () =>
              run(async () => {
                const result = await client.DELETE(
                  '/tenants/{tenant_id}/events/{event_id}/relationships/{other_event_id}',
                  {
                    params: {
                      path: { ...path, other_event_id: otherId },
                      query: { kind: row.kind, direction: incoming ? 'incoming' : 'outgoing' },
                      header: { 'if-match': version },
                    },
                  },
                );
                render(await unwrap(result));
                version = result.response.headers.get('etag') ?? '';
                comparison.replaceChildren();
                status.say('Relationship removed.');
              }),
            true,
            'close',
          ),
        );
      }
      assertions.append(line);
    }
  }
  async function refresh() {
    const result = await client.GET('/tenants/{tenant_id}/events/{event_id}/relationships', {
      params: { path },
    });
    render(await unwrap(result));
    version = result.response.headers.get('etag') ?? '';
    comparison.replaceChildren();
  }
  try {
    await refresh();
  } catch (error) {
    if (error instanceof LorenzoApiError && error.status === 403) return null;
    throw error;
  }
  const search = el('div', '', 'stack-tight');
  search.append(
    query.label,
    button(
      'Search Events',
      () =>
        run(async () => {
          const page = await unwrap(
            await client.GET('/tenants/{tenant_id}/entities', {
              params: {
                path: { tenant_id: tenantId },
                query: { q: query.input.value, kind: ['event'], size: 30 },
              },
            }),
          );
          results.replaceChildren();
          for (const entry of page.items.filter((e) => e.id !== eventId))
            results.append(
              button(
                entry.name,
                () => {
                  target = { id: entry.id, name: entry.name };
                  selected.textContent = `Selected Event: ${entry.name}`;
                  comparison.replaceChildren();
                },
                true,
              ),
            );
          status.say(page.total ? 'Choose an Event from the results.' : 'No matching Events.');
        }),
      true,
      'search',
    ),
    results,
    selected,
  );
  const actions = el('div', '', 'row');
  if (canEdit)
    actions.append(
      button(
        'Add relationship',
        () =>
          run(async () => {
            if (!target) throw new Error('Choose an Event first.');
            if (!version) throw new Error('Refresh the saved relationships first.');
            const value = relationship.input.value;
            const result = await client.PUT(
              '/tenants/{tenant_id}/events/{event_id}/relationships/{other_event_id}',
              {
                params: {
                  path: { ...path, other_event_id: target.id },
                  header: { 'if-match': version },
                },
                body: {
                  kind: value === 'causes' || value === 'caused-by' ? 'causes' : 'order',
                  direction: value === 'after' || value === 'caused-by' ? 'incoming' : 'outgoing',
                },
              },
            );
            render(await unwrap(result));
            version = result.response.headers.get('etag') ?? '';
            comparison.replaceChildren();
            status.say('Relationship recorded.');
          }),
        false,
        'add',
      ),
    );
  actions.append(
    button(
      'Compare Events',
      () =>
        run(async () => {
          if (!target) throw new Error('Choose an Event first.');
          const [result] = await unwrap(
            await client.POST('/tenants/{tenant_id}/events/compare', {
              params: { path: { tenant_id: tenantId } },
              body: { pairs: [{ left: eventId, right: target.id }] },
            }),
          );
          const basis = {
            causal: 'Causal · a recorded chain of causes',
            ruled: 'Ruled · recorded ordering',
            linearized: canEdit
              ? 'Linearized · no recorded ordering path'
              : 'Linearized · no visible recorded ordering path',
            identity: 'Same Event',
          }[result.basis];
          comparison.replaceChildren(
            el('p', `This Event is ${result.relation} ${target.name}. ${basis}.`),
          );
          if (result.basis === 'linearized')
            comparison.append(
              el(
                'p',
                'This is a deterministic display order, not evidence of what happened first. Adding a relationship can change it.',
                'caption',
              ),
            );
          for (const edge of result.path) {
            const line = el('p');
            line.append(
              link(edge.from_name, entryHref(tenantId, edge.from_event_id)),
              document.createTextNode(edge.kind === 'causes' ? ' caused ' : ' happened before '),
              link(edge.to_name, entryHref(tenantId, edge.to_event_id)),
            );
            if (edge.evidence === 'lived')
              line.append(
                document.createTextNode(
                  ` · Lived order of ${edge.being_name ?? 'a participating being'}`,
                ),
              );
            comparison.append(line);
          }
        }),
      true,
      'compare',
    ),
    button(
      'Refresh saved relationships',
      () =>
        run(async () => {
          await refresh();
          status.say('Saved relationships refreshed. Your selection is kept.');
        }),
      true,
      'refresh',
    ),
  );
  body.append(
    el(
      'p',
      canEdit
        ? 'Record what happened before or caused this Event. Relationships start private; sharing never opens an Event or its notes.'
        : 'Only shared relationships between Events you can see appear here. This order may differ from another reader’s view. Calendar dates do not establish order.',
      'caption',
    ),
    assertions,
    none,
    search,
    ...(canEdit ? [relationship.label] : []),
    actions,
    comparison,
    status.node,
  );
  return host;
}
