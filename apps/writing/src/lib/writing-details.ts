import { client, unwrap } from './api';
import { outlineOf, writingAddress } from './composition';

const node = <K extends keyof HTMLElementTagNameMap>(tag: K, text = '') => {
  const el = document.createElement(tag);
  el.textContent = text;
  return el;
};

export async function writingDetails(
  host: HTMLElement,
  tenant: string,
  id: string,
  onTellingChanged?: (version: string) => void,
) {
  const current = await outlineOf(tenant, id);
  const status = node('p');
  status.setAttribute('role', 'status');
  host.replaceChildren(status);
  const action = (label: string, run: () => Promise<void>) => {
    const button = node('button', label);
    button.type = 'button';
    button.className = 'btn btn-secondary';
    button.addEventListener('click', () => {
      button.disabled = true;
      void run()
        .catch((error) => {
          status.textContent = error instanceof Error ? error.message : 'This could not be saved.';
        })
        .finally(() => {
          button.disabled = false;
        });
    });
    return button;
  };
  const choose = (
    label: string,
    kind: 'being' | 'fact' | 'event' | 'calendar_period',
    selected: (id: string) => Promise<void>,
  ) => {
    const details = node('details');
    details.append(node('summary', label));
    const input = node('input');
    input.type = 'search';
    input.className = 'text-input';
    input.setAttribute('aria-label', label);
    const results = node('div');
    results.className = 'stack-tight';
    details.append(
      input,
      action(`Find ${label.toLowerCase()}`, async () => {
        const found = await unwrap(
          await client.GET('/tenants/{tenant_id}/entities', {
            params: {
              path: { tenant_id: tenant },
              query: { q: input.value.trim(), kind: [kind], size: 10 },
            },
          }),
        );
        results.replaceChildren();
        for (const entry of found.items)
          results.append(
            action(entry.name, async () => {
              await selected(entry.id);
              await writingDetails(host, tenant, id, onTellingChanged);
            }),
          );
        if (!found.items.length) results.append(node('p', 'No matching entries.'));
        if (found.total > 10) results.append(node('p', 'Refine the name to find more entries.'));
      }),
      results,
    );
    host.append(details);
  };
  if (current.kind === 'scene_telling') {
    if (current.viewpoint_id) {
      const being = await unwrap(
        await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
          params: { path: { tenant_id: tenant, entity_id: current.viewpoint_id } },
        }),
      );
      host.append(node('p', `Viewpoint: ${being.name}`));
    } else host.append(node('p', 'No viewpoint selected.'));
    const setViewpoint = async (viewpoint_id: string | null) => {
      const updated = await unwrap(
        await client.PUT('/tenants/{tenant_id}/writing/tellings/{id}/viewpoint', {
          params: { path: { tenant_id: tenant, id }, header: { 'if-match': current.version } },
          body: { viewpoint_id },
        }),
      );
      onTellingChanged?.(updated.version);
    };
    choose('Viewpoint', 'being', setViewpoint);
    if (current.viewpoint_id)
      host.append(
        action('Clear viewpoint', async () => {
          await setViewpoint(null);
          await writingDetails(host, tenant, id, onTellingChanged);
        }),
      );
  }
  const scene = current.kind === 'scene' ? id : current.scene_id;
  if (!scene) return;
  if (current.kind === 'scene_telling') {
    const link = node('a', 'Shared Scene');
    link.href = writingAddress(tenant, scene);
    host.append(link);
    host.append(node('p', 'These world references belong to the shared Scene.'));
  }
  const path = { tenant_id: tenant, source_kind: 'scenes' as const, source_id: scene };
  const response = await client.GET('/tenants/{tenant_id}/{source_kind}/{source_id}/references', {
    params: { path },
  });
  const references = await unwrap(response);
  const version = response.response.headers.get('etag');
  const list = node('ul');
  host.append(list);
  for (const ref of references) {
    const item = node('li', `${ref.name} (${ref.kind}) `);
    if (version) {
      item.append(
        action('Remove reference', async () => {
          await unwrap(
            await client.DELETE(
              '/tenants/{tenant_id}/{source_kind}/{source_id}/references/{kind}/{target_id}',
              {
                params: {
                  path: { ...path, kind: ref.kind, target_id: ref.id },
                  header: { 'if-match': version },
                },
              },
            ),
          );
          await writingDetails(host, tenant, id, onTellingChanged);
        }),
      );
    }
    list.append(item);
  }
  if (!version) return;
  for (const [label, kind, plural] of [
    ['Being', 'being', 'beings'],
    ['Fact', 'fact', 'facts'],
    ['Event', 'event', 'events'],
  ] as const) {
    choose(label, kind, async (target) => {
      await unwrap(
        await client.PUT(
          '/tenants/{tenant_id}/{source_kind}/{source_id}/references/{kind}/{target_id}',
          {
            params: {
              path: { ...path, kind: plural, target_id: target },
              header: { 'if-match': version },
            },
            body: { is_shared: false },
          },
        ),
      );
    });
  }
  const sceneResponse = await client.GET('/tenants/{tenant_id}/scenes/{scene_id}', {
    params: { path: { tenant_id: tenant, scene_id: scene } },
  });
  const sceneInfo = await unwrap(sceneResponse);
  const setPeriod = async (period_entity_id: string | null) => {
    await unwrap(
      await client.PATCH('/tenants/{tenant_id}/scenes/{scene_id}', {
        params: {
          path: { tenant_id: tenant, scene_id: scene },
          header: { 'if-match': sceneResponse.response.headers.get('etag') ?? '' },
        },
        body: { period_entity_id },
      }),
    );
  };
  if (sceneInfo.period_entity_id) {
    const period = await unwrap(
      await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
        params: { path: { tenant_id: tenant, entity_id: sceneInfo.period_entity_id } },
      }),
    );
    host.append(
      node('p', `Period: ${period.name}`),
      action('Clear period', async () => {
        await setPeriod(null);
        await writingDetails(host, tenant, id, onTellingChanged);
      }),
    );
  }
  choose('Period', 'calendar_period', setPeriod);
}
