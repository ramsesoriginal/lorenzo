import { client, fetchAllPages, unwrap } from './api';
import {
  actions,
  audienceBadge,
  button,
  el,
  empty,
  groupTitle,
  panel,
  say,
  sectionHead,
  select,
  statusLine,
} from './dom';

type Source = 'scenes' | 'sessions';
const KIND: Record<string, string> = { facts: 'Fact', events: 'Event', beings: 'Being' };
const kindName = (kind: string) => KIND[kind] ?? kind;

/** `level` is 2 for a section of the page and 4 for the group inside a Scene's card. */
export async function referencePanel(
  tenant: string,
  source: Source,
  id: string,
  manager: boolean,
  refresh: () => Promise<void>,
  level: 2 | 4 = 2,
) {
  const path = { tenant_id: tenant, source_kind: source, source_id: id };
  const result = await client.GET('/tenants/{tenant_id}/{source_kind}/{source_id}/references', {
    params: { path },
    cache: 'no-store',
  });
  const rows = await unwrap(result);
  let version = result.response.headers.get('etag') ?? '';
  const host = el('div', '', 'stack');
  const title = source === 'scenes' ? 'Scene references and participants' : 'Session references';
  host.append(level === 2 ? sectionHead(title, { count: rows.length }) : groupTitle('h4', title));
  const list = el('ul', '', 'list');
  for (const row of rows) {
    const item = el('li');
    const name = el('span', row.name, 'grow');
    item.append(
      name,
      el('span', kindName(row.kind), 'chip'),
      audienceBadge(row.is_shared ? 'Shared' : 'Private', row.is_shared),
    );
    if (manager)
      item.append(
        button(row.is_shared ? 'Make relationship private' : 'Share relationship', async () => {
          await unwrap(
            await client.PUT(
              '/tenants/{tenant_id}/{source_kind}/{source_id}/references/{kind}/{target_id}',
              {
                params: {
                  path: { ...path, kind: row.kind, target_id: row.id },
                  header: { 'if-match': version },
                },
                body: { is_shared: !row.is_shared },
              },
            ),
          );
          await refresh();
        }),
        button('Remove reference', async () => {
          await unwrap(
            await client.DELETE(
              '/tenants/{tenant_id}/{source_kind}/{source_id}/references/{kind}/{target_id}',
              {
                params: {
                  path: { ...path, kind: row.kind, target_id: row.id },
                  header: { 'if-match': version },
                },
              },
            ),
          );
          await refresh();
        }),
      );
    list.append(item);
  }
  if (rows.length) host.append(list);
  else host.append(empty('No references are available to you here.'));
  if (!manager) return host;
  const entries = await fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/entities', {
        params: {
          path: { tenant_id: tenant },
          query: {
            kind: source === 'scenes' ? ['fact', 'event', 'being'] : ['fact', 'event'],
            page,
            size: 100,
          },
        },
      }),
    ),
  );
  const choices = entries.flatMap((entry) =>
    entry.kinds
      .filter(
        (kind) => kind === 'fact' || kind === 'event' || (kind === 'being' && source === 'scenes'),
      )
      .map((kind) => ({
        id: entry.id,
        kind: `${kind}s` as 'facts' | 'events' | 'beings',
        name: entry.name,
      })),
  );
  const picker = select(
    'Reference to add',
    choices.map((e, i) => [String(i), `${e.name} · ${kindName(e.kind)}`]),
  );
  const status = statusLine();
  const form = el('div', '', 'stack-tight');
  form.append(
    picker.label,
    el(
      'p',
      'New relationships are private. Sharing still requires access to both entries. References do not record learning or Event participation.',
      'status-text',
    ),
    actions(
      button(
        'Add reference',
        async () => {
          const chosen = choices[Number(picker.input.value)];
          if (!chosen) return;
          await unwrap(
            await client.PUT(
              '/tenants/{tenant_id}/{source_kind}/{source_id}/references/{kind}/{target_id}',
              {
                params: {
                  path: { ...path, kind: chosen.kind, target_id: chosen.id },
                  header: { 'if-match': version },
                },
                body: { is_shared: false },
              },
            ),
          );
          await refresh();
        },
        { variant: 'primary', icon: 'add' },
      ),
      button('Review saved references', async () => {
        const saved = await client.GET(
          '/tenants/{tenant_id}/{source_kind}/{source_id}/references',
          { params: { path }, cache: 'no-store' },
        );
        const current = await unwrap(saved);
        version = saved.response.headers.get('etag') ?? '';
        say(
          status,
          `Saved references: ${current.map((r) => r.name).join(', ') || 'none'}. Your selection is unchanged. Review before retrying.`,
        );
      }),
    ),
    status,
  );
  host.append(form);
  return host;
}

export async function coveragePanel(
  tenant: string,
  id: string,
  manager: boolean,
  refresh: () => Promise<void>,
) {
  const path = { tenant_id: tenant, entity_id: id };
  const result = await client.GET('/tenants/{tenant_id}/entities/{entity_id}/dates', {
    params: { path },
    cache: 'no-store',
  });
  const periods = await unwrap(result);
  const host = el('div', '', 'stack');
  host.append(sectionHead('Game time covered', { count: periods.length }));
  if (periods.length) {
    const list = el('ul', '', 'row');
    for (const p of periods) list.append(el('li', p.name, 'chip'));
    host.append(list);
  } else host.append(empty('No game time is set for this Session.'));
  if (!manager) return host;
  const entries = await fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/entities', {
        params: {
          path: { tenant_id: tenant },
          query: { kind: ['calendar_period'], page, size: 100 },
        },
      }),
    ),
  );
  const choose = panel('Choose periods', `${entries.length} available`);
  const checks = el('div', '', 'grid');
  checks.style.setProperty('--grid-min', '240px');
  const boxes = entries.map((e) => {
    const label = el('label', '', 'check');
    const input = el('input');
    input.type = 'checkbox';
    input.checked = periods.some((p) => p.entity_id === e.id);
    label.append(input, el('span', e.name));
    checks.append(label);
    return { id: e.id, input };
  });
  const entry = await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
    params: { path },
    cache: 'no-store',
  });
  await unwrap(entry);
  let version = entry.response.headers.get('etag') ?? '';
  const status = statusLine();
  if (!entries.length) choose.body.append(empty('No calendar periods exist in this library yet.'));
  choose.body.append(
    checks,
    actions(
      button(
        'Save game time',
        async () => {
          await unwrap(
            await client.PUT('/tenants/{tenant_id}/entities/{entity_id}/dates', {
              params: { path, header: { 'if-match': version } },
              body: { period_ids: boxes.filter((c) => c.input.checked).map((c) => c.id) },
            }),
          );
          await refresh();
        },
        { variant: 'primary' },
      ),
      button('Review saved game time', async () => {
        const saved = await client.GET('/tenants/{tenant_id}/entities/{entity_id}/dates', {
          params: { path },
          cache: 'no-store',
        });
        const values = await unwrap(saved);
        const current = await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
          params: { path },
          cache: 'no-store',
        });
        await unwrap(current);
        version = current.response.headers.get('etag') ?? '';
        say(
          status,
          `Saved periods: ${values.map((p) => p.name).join(', ') || 'none'}. Your draft is unchanged.`,
        );
      }),
    ),
    status,
  );
  host.append(choose.root);
  return host;
}
