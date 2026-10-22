import { client, fetchAllPages, unwrap } from './api';
import { referencePanel } from './context';
import {
  actions,
  backLink,
  button,
  card,
  el,
  empty,
  errorNotice,
  field,
  link,
  loading,
  pageHead,
  panel,
  say,
  sectionHead,
  select,
  statusLine,
  suspendControls,
} from './dom';
import { libraryName } from './names';
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
    host.replaceChildren(loading('Opening the Scenes of this library…'));
    const tenant = await tenantAddress(new URLSearchParams(location.search).get('tenant') ?? '');
    const entries = await fetchAllPages(async (page) =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/entities', {
          params: { path: { tenant_id: tenant }, query: { kind: ['scene'], page, size: 100 } },
        }),
      ),
    );
    const view = el('div', '', 'stack view');
    view.append(
      pageHead('Reusable Scenes', {
        crumbs: [backLink('My Sessions', '/')],
        lede: (await libraryName(tenant)) ?? undefined,
      }),
    );
    if (entries.length) {
      const list = el('ul', '', 'list');
      for (const entry of entries) {
        const row = el('li');
        const name = link(entry.name, href(tenant, entry.id));
        name.classList.add('grow');
        row.append(name);
        list.append(row);
      }
      view.append(list);
    } else view.append(empty('No reusable Scenes exist in this library yet.'));
    host.replaceChildren(view);
    const managed = await unwrap(await client.GET('/me/managed'));
    if (
      !managed.tenants.some(
        (t) => t.tenant_id === tenant && (t.role !== null || t.campaigns.some((c) => c.is_gm)),
      )
    )
      return;
    const name = field('Scene title');
    const slug = field('Link name (optional)');
    const id = crypto.randomUUID();
    const grid = el('div', '', 'grid');
    grid.style.setProperty('--grid-min', '240px');
    grid.append(name.label, slug.label);
    const form = el('section', '', 'stack');
    form.append(
      sectionHead('Create a reusable Scene'),
      card(
        grid,
        actions(
          button(
            'Create Scene',
            async () => {
              if (!name.input.value.trim()) throw new Error('Give the Scene a title.');
              const created = await unwrap(
                await client.POST('/tenants/{tenant_id}/scenes', {
                  params: { path: { tenant_id: tenant } },
                  body: {
                    id,
                    name: name.input.value,
                    slug: slug.input.value || null,
                    is_public: false,
                  },
                }),
              );
              location.assign(href(tenant, created.id, slug.input.value));
            },
            { variant: 'primary', icon: 'add' },
          ),
        ),
      ).root,
    );
    view.append(form);
  } catch (error) {
    host.querySelector('[data-loading]')?.remove();
    host.append(errorNotice(error));
  }
}
export async function mountScene() {
  const host = document.querySelector<HTMLElement>('#scene-view');
  if (!host || !(await start())) return;
  try {
    host.replaceChildren(loading('Opening this Scene…'));
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
      if (!found) throw new Error('This Scene is not available.');
      id = found.entity_id;
    }
    const path = { tenant_id: tenant, scene_id: id };
    let generation = 0;
    let releaseControls: (() => void) | undefined;
    const refresh = async () => {
      const turn = ++generation;
      releaseControls ??= suspendControls(host);
      try {
        const view = el('div', '', 'stack view');
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
          pageHead(scene.name, {
            crumbs: [backLink('Reusable Scenes', `/scenes/?${new URLSearchParams({ tenant })}`)],
            lede: (await libraryName(tenant)) ?? undefined,
          }),
        );
        if (scene.can_manage) {
          const details = panel('Scene details', 'title, link name, audience, period');
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
          const status = statusLine();
          const grid = el('div', '', 'grid');
          grid.style.setProperty('--grid-min', '240px');
          grid.append(name.label, slug.label, period.label);
          details.body.append(
            grid,
            shared.label,
            actions(
              button(
                'Save Scene',
                async () => {
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
                },
                { variant: 'primary' },
              ),
              button('Review saved Scene', async () => {
                const saved = await client.GET('/tenants/{tenant_id}/scenes/{scene_id}', {
                  params: { path },
                  cache: 'no-store',
                });
                const current = await unwrap(saved);
                version = saved.response.headers.get('etag') ?? '';
                say(
                  status,
                  `Saved Scene: ${current.name}; link name ${current.slug ?? 'not set'}. Your draft is unchanged. Review before retrying.`,
                );
              }),
            ),
            status,
          );
          view.append(details.root);
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
    host.querySelector('[data-loading]')?.remove();
    host.append(errorNotice(error));
  }
}
