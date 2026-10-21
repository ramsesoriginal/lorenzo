import { client, type components, LorenzoApiError, unwrap } from './api';
import { button, el, entryHref, field, link, message, select } from './dom';

type Relationship = components['schemas']['RelationshipOut'];

/** Reader graph with separately gated staff editing; the API remains authoritative. */
export async function eventOrder(
  tenantId: string,
  eventId: string,
  canEdit = false,
): Promise<HTMLElement | null> {
  const path = { tenant_id: tenantId, event_id: eventId };
  const host = el('details', '', 'panel stack');
  host.dataset.eventOrder = '';
  const body = el('div', '', 'stack');
  host.append(el('summary', 'Order and causes'), body);
  const assertions = el('div', '', 'stack-tight');
  const status = el('p');
  status.setAttribute('role', 'status');
  let version = '';
  let busy = false;
  const query = field('Find an Event');
  const results = el('div', '', 'stack-tight');
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
    status.textContent = '';
    try {
      await action();
    } catch (error) {
      status.textContent = canEdit
        ? `${message(error)} Your selection is kept. Refresh the saved relationships before retrying a conflicting edit.`
        : message(error);
    } finally {
      busy = false;
    }
  }
  function render(rows: Relationship[]) {
    assertions.replaceChildren();
    if (!rows.length)
      assertions.append(
        el(
          'p',
          canEdit
            ? 'No ordering relationships recorded.'
            : 'No shared relationships are available in your view.',
          'caption',
        ),
      );
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
      const line = el('div', '', 'row');
      line.append(el('span', label), link(otherName, entryHref(tenantId, otherId)));
      if (canEdit)
        line.append(
          el(
            'span',
            row.is_shared ? 'Shared with readers of both Events' : 'Private relationship',
            'caption',
          ),
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
                status.textContent = row.is_shared
                  ? 'Relationship is private.'
                  : 'Relationship shared. Readers still need access to both Events.';
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
                status.textContent = 'Relationship removed.';
              }),
            true,
          ),
        );
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
  body.append(
    el(
      'p',
      canEdit
        ? 'Record what happened before or caused this Event. Relationships start private; sharing never opens an Event or its Information.'
        : 'Only shared relationships between Events you can see appear here. This order may differ from another reader’s view. Calendar dates do not establish order.',
      'caption',
    ),
    assertions,
    button(
      'Refresh saved relationships',
      () =>
        run(async () => {
          await refresh();
          status.textContent = 'Saved relationships refreshed. Your selection is kept.';
        }),
      true,
    ),
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
          status.textContent = page.total
            ? 'Choose an Event from the results.'
            : 'No matching Events.';
        }),
      true,
    ),
    results,
    selected,
    ...(canEdit
      ? [
          relationship.label,
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
                      direction:
                        value === 'after' || value === 'caused-by' ? 'incoming' : 'outgoing',
                    },
                  },
                );
                render(await unwrap(result));
                version = result.response.headers.get('etag') ?? '';
                comparison.replaceChildren();
                status.textContent = 'Relationship recorded.';
              }),
            true,
          ),
        ]
      : []),
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
            comparison.append(line);
          }
        }),
      true,
    ),
    comparison,
    status,
  );
  return host;
}
