import { client, fetchAllPages, unwrap } from './api';
import { button, el, select } from './dom';

type Source = 'scenes' | 'sessions';
export async function referencePanel(
  tenant: string,
  source: Source,
  id: string,
  manager: boolean,
  refresh: () => Promise<void>,
) {
  const path = { tenant_id: tenant, source_kind: source, source_id: id };
  const result = await client.GET('/tenants/{tenant_id}/{source_kind}/{source_id}/references', {
    params: { path },
    cache: 'no-store',
  });
  const rows = await unwrap(result);
  let version = result.response.headers.get('etag') ?? '';
  const host = el('section', '', 'panel stack');
  host.append(
    el(
      'h3',
      source === 'scenes' ? 'Scene references and participants' : 'Direct session references',
    ),
  );
  const list = el('ul', '', 'stack-tight');
  for (const row of rows) {
    const item = el('li', '', 'stack-tight');
    item.append(
      el(
        'p',
        `${row.name} · ${row.kind} · ${row.is_shared ? 'Shared relationship' : 'Private relationship'}`,
      ),
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
  host.append(list);
  if (!rows.length) host.append(el('p', 'No references are available to you here.', 'caption'));
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
    choices.map((e, i) => [String(i), `${e.name} · ${e.kind}`]),
  );
  const status = el('p');
  status.setAttribute('role', 'status');
  host.append(
    picker.label,
    el(
      'p',
      'New relationships are private. Sharing still requires access to both entries. References do not record learning or Event participation.',
      'caption',
    ),
    button('Review saved references', async () => {
      const saved = await client.GET('/tenants/{tenant_id}/{source_kind}/{source_id}/references', {
        params: { path },
        cache: 'no-store',
      });
      const current = await unwrap(saved);
      version = saved.response.headers.get('etag') ?? '';
      status.textContent = `Saved references: ${current.map((r) => r.name).join(', ') || 'none'}. Your selection is unchanged. Review before retrying.`;
    }),
    button('Add reference', async () => {
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
    }),
    status,
  );
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
  const host = el('section', '', 'panel stack');
  host.append(el('h3', 'Game time covered'));
  const list = el('ul');
  for (const p of periods) list.append(el('li', p.name));
  host.append(list);
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
  const checks = entries.map((e) => {
    const label = el('label', e.name);
    const input = el('input');
    input.type = 'checkbox';
    input.checked = periods.some((p) => p.entity_id === e.id);
    label.prepend(input);
    host.append(label);
    return { id: e.id, input };
  });
  const entry = await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
    params: { path },
    cache: 'no-store',
  });
  await unwrap(entry);
  let version = entry.response.headers.get('etag') ?? '';
  const status = el('p');
  status.setAttribute('role', 'status');
  host.append(
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
      status.textContent = `Saved periods: ${values.map((p) => p.name).join(', ') || 'none'}. Your draft is unchanged.`;
    }),
    button('Save game time', async () => {
      await unwrap(
        await client.PUT('/tenants/{tenant_id}/entities/{entity_id}/dates', {
          params: { path, header: { 'if-match': version } },
          body: { period_ids: checks.filter((c) => c.input.checked).map((c) => c.id) },
        }),
      );
      await refresh();
    }),
    status,
  );
  return host;
}
