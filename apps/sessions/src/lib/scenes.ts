import { client, fetchAllPages, unwrap } from './api';
import { kindName, referencePanel } from './context';
import {
  actions,
  backLink,
  button,
  card,
  el,
  empty,
  errorNotice,
  field,
  icon,
  link,
  loading,
  pageHead,
  panel,
  say,
  sectionHead,
  statusLine,
  suspendControls,
} from './dom';
import { libraryName } from './names';
import { notes } from './notes';
import { periodControl } from './periods';
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
      // Cards, as on the Sessions Home: the title, who can see it, where it is in the world and what
      // it refers to. The details are read for each card and never held up on.
      const list = el('ul', '', 'list home-list scene-list');
      for (const entry of entries) {
        const row = el('li', '', 'row scene-card');
        row.append(icon('kind-chapter'));
        const text = el('div', '', 'stack-tight grow');
        const meta = el('p', '', 'status-text');
        text.append(link(entry.name, href(tenant, entry.id)), meta);
        row.append(text);
        const path = { tenant_id: tenant, scene_id: entry.id };
        void Promise.all([
          client.GET('/tenants/{tenant_id}/scenes/{scene_id}', { params: { path } }),
          client.GET('/tenants/{tenant_id}/{source_kind}/{source_id}/references', {
            params: { path: { tenant_id: tenant, source_kind: 'scenes', source_id: entry.id } },
          }),
        ])
          .then(async ([scene, references]) => {
            const parts: string[] = [];
            if (scene.data?.period_entity_id) {
              const period = await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
                params: { path: { tenant_id: tenant, entity_id: scene.data.period_entity_id } },
              });
              if (period.data?.name) parts.push(period.data.name);
            }
            const counts = new Map<string, number>();
            for (const r of references.data ?? [])
              counts.set(r.kind, (counts.get(r.kind) ?? 0) + 1);
            if (counts.size)
              parts.push([...counts].map(([kind, n]) => `${n} ${kindName(kind)}`).join(', '));
            meta.textContent = parts.join(' · ') || 'Not tied to a period, nothing referenced yet';
            if (scene.data)
              row.append(
                el('span', scene.data.is_public ? 'Visible in this library' : 'Private', 'chip'),
              );
          })
          .catch(() => {});
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
        const grid = el('div', '', 'session-grid');
        if (scene.can_manage) {
          const details = panel('Scene details', 'title, link name, audience, period');
          const name = field('Scene title', scene.name);
          const slug = field('Link name', scene.slug ?? '');
          const shared = field('Visible in this library', '', 'checkbox');
          shared.input.checked = scene.is_public;
          const period = periodControl({
            tenant,
            label: 'Scene period',
            mode: 'single',
            initial: scene.period_entity_id ? [scene.period_entity_id] : [],
          });
          const status = statusLine();
          const fieldGrid = el('div', '', 'grid');
          fieldGrid.style.setProperty('--grid-min', '240px');
          fieldGrid.append(name.label, slug.label, period.root);
          details.body.append(
            fieldGrid,
            shared.label,
            actions(
              button(
                'Save Scene',
                async () => {
                  const picked = await period.value();
                  await unwrap(
                    await client.PATCH('/tenants/{tenant_id}/scenes/{scene_id}', {
                      params: { path, header: { 'if-match': version } },
                      body: {
                        name: name.input.value,
                        slug: slug.input.value || null,
                        is_public: shared.input.checked,
                        ...(picked !== null ? { period_entity_id: picked[0] ?? null } : {}),
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
          grid.append(details.root);
        }
        grid.append(
          await referencePanel(tenant, 'scenes', id, scene.can_manage, refresh),
          await notes(tenant, id, () => void refresh(), 'scene'),
        );
        // The parts of a Scene are cards in two columns where there is room (screen 21).
        for (const [index, node] of [...grid.children].entries())
          (node as HTMLElement).dataset.region = `scene-part-${index}`;
        view.append(grid);
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
