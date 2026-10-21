import { client, fetchAllPages, unwrap } from './api';
import { referencePanel } from './context';
import { button, el, field, link, message, select, suspendControls } from './dom';
import { notes } from './notes';
import { start } from './sign-in';

const href = (tenant: string, id: string, slug?: string | null) =>
  `/scene/?${new URLSearchParams({ tenant, ...(slug ? { slug } : { id }) })}`;
async function tenantAddress(value: string) {
  if (/^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(value)) return value;
  const tenants = await fetchAllPages(async (page) =>
    unwrap(await client.GET('/tenants', { params: { query: { page, size: 100 } } })),
  );
  const found = tenants.find((t) => t.slug === value);
  if (!found) throw new Error('This library is not available.');
  return found.id;
}
export async function mountScenes() {
  const host = document.querySelector<HTMLElement>('#scenes-view');
  if (!host || !(await start())) return;
  try {
    const tenant = await tenantAddress(new URLSearchParams(location.search).get('tenant') ?? '');
    const entries = await fetchAllPages(async (page) =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/entities', {
          params: { path: { tenant_id: tenant }, query: { kind: ['scene'], page, size: 100 } },
        }),
      ),
    );
    host.replaceChildren(link('My sessions', '/'), el('h1', 'Reusable scenes'));
    const list = el('ul', '', 'stack');
    for (const entry of entries) {
      const row = el('li');
      row.append(link(entry.name, href(tenant, entry.id)));
      list.append(row);
    }
    host.append(list);
    const managed = await unwrap(await client.GET('/me/managed'));
    if (
      !managed.tenants.some(
        (t) => t.tenant_id === tenant && (t.role !== null || t.campaigns.some((c) => c.is_gm)),
      )
    )
      return;
    const form = el('section', '', 'panel stack');
    form.append(el('h2', 'Create a reusable scene'));
    const name = field('Scene title');
    const slug = field('Link name (optional)');
    const id = crypto.randomUUID();
    form.append(
      name.label,
      slug.label,
      button('Create scene', async () => {
        if (!name.input.value.trim()) throw new Error('Give the scene a title.');
        const created = await unwrap(
          await client.POST('/tenants/{tenant_id}/scenes', {
            params: { path: { tenant_id: tenant } },
            body: { id, name: name.input.value, slug: slug.input.value || null, is_public: false },
          }),
        );
        location.assign(href(tenant, created.id, slug.input.value));
      }),
    );
    host.append(form);
  } catch (error) {
    host.append(el('p', message(error)));
  }
}
export async function mountScene() {
  const host = document.querySelector<HTMLElement>('#scene-view');
  if (!host || !(await start())) return;
  try {
    const query = new URLSearchParams(location.search);
    const tenant = await tenantAddress(query.get('tenant') ?? '');
    let id = query.get('id') ?? '';
    const slug = query.get('slug');
    if (slug || !/^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(id)) {
      const entries = await unwrap(
        await client.GET('/tenants/{tenant_id}/entities/resolve', {
          params: { path: { tenant_id: tenant }, query: { slug: [slug ?? id] } },
        }),
      );
      const found = entries.find((e) => e.slug === (slug ?? id) && e.kinds.includes('scene'));
      if (!found) throw new Error('This scene is not available.');
      id = found.entity_id;
    }
    const path = { tenant_id: tenant, scene_id: id };
    let generation = 0;
    let releaseControls: (() => void) | undefined;
    const refresh = async () => {
      const turn = ++generation;
      releaseControls ??= suspendControls(host);
      try {
        const view = el('div', '', 'stack');
        const publish = () => {
          if (host.isConnected && turn === generation) host.replaceChildren(...view.childNodes);
        };
        const result = await client.GET('/tenants/{tenant_id}/scenes/{scene_id}', {
          params: { path },
          cache: 'no-store',
        });
        const scene = await unwrap(result);
        let version = result.response.headers.get('etag') ?? '';
        history.replaceState(history.state, '', href(tenant, id, scene.slug));
        view.replaceChildren(
          link('Reusable scenes', `/scenes/?${new URLSearchParams({ tenant })}`),
          el('h1', scene.name),
        );
        if (scene.can_manage) {
          const details = el('details', '', 'panel stack');
          details.append(el('summary', 'Scene details'));
          const name = field('Scene title', scene.name);
          const slug = field('Link name', scene.slug ?? '');
          const shared = field('Visible in this library', '', 'checkbox');
          shared.input.checked = scene.is_public;
          const periods = await fetchAllPages(async (page) =>
            unwrap(
              await client.GET('/tenants/{tenant_id}/entities', {
                params: {
                  path: { tenant_id: tenant },
                  query: { kind: ['calendar_period'], page, size: 100 },
                },
              }),
            ),
          );
          const period = select(
            'Scene period',
            [['', 'Not set'], ...periods.map((p) => [p.id, p.name] as [string, string])],
            scene.period_entity_id ?? '',
          );
          const status = el('p');
          status.setAttribute('role', 'status');
          details.append(
            name.label,
            slug.label,
            shared.label,
            period.label,
            button('Review saved scene', async () => {
              const saved = await client.GET('/tenants/{tenant_id}/scenes/{scene_id}', {
                params: { path },
                cache: 'no-store',
              });
              const current = await unwrap(saved);
              version = saved.response.headers.get('etag') ?? '';
              status.textContent = `Saved scene: ${current.name}; link name ${current.slug ?? 'not set'}. Your draft is unchanged. Review before retrying.`;
            }),
            button('Save scene', async () => {
              await unwrap(
                await client.PATCH('/tenants/{tenant_id}/scenes/{scene_id}', {
                  params: { path, header: { 'if-match': version } },
                  body: {
                    name: name.input.value,
                    slug: slug.input.value || null,
                    is_public: shared.input.checked,
                    ...(period.input.value !== (scene.period_entity_id ?? '')
                      ? { period_entity_id: period.input.value || null }
                      : {}),
                  },
                }),
              );
              await refresh();
            }),
            status,
          );
          view.append(details);
        }
        view.append(
          await referencePanel(tenant, 'scenes', id, scene.can_manage, refresh),
          await notes(tenant, id, () => void refresh(), 'scene'),
        );
        publish();
      } finally {
        if (turn === generation) {
          releaseControls?.();
          releaseControls = undefined;
        }
      }
    };
    await refresh();
  } catch (error) {
    host.append(el('p', message(error)));
  }
}
