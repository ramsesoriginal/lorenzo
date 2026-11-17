import { client, LorenzoApiError, unwrap } from './api';
import { manuscriptPassages } from './manuscript-count';
import { mentioned, nameKey } from './mentioned-names';

type Being = { id: string; name: string };

export function suggestedBeings(
  tenant: string,
  scene: string,
  sources: () => string[],
  refresh: () => Promise<void>,
) {
  const panel = document.createElement('details');
  const summary = document.createElement('summary');
  summary.textContent = 'Suggested Being references';
  const controls = document.createElement('fieldset');
  const legend = document.createElement('legend');
  legend.textContent = 'Names in this Scene';
  const check = document.createElement('button');
  check.type = 'button';
  check.className = 'btn btn-secondary';
  check.textContent = 'Check names';
  const results = document.createElement('div');
  results.className = 'stack-tight';
  const status = document.createElement('p');
  status.setAttribute('role', 'status');
  controls.append(legend, check, results);
  panel.append(summary, controls, status);
  const path = { tenant_id: tenant, source_kind: 'scenes' as const, source_id: scene };

  async function run(operation: () => Promise<void>) {
    if (controls.disabled) return;
    controls.disabled = true;
    try {
      await operation();
    } catch (error) {
      results.replaceChildren();
      status.textContent =
        error instanceof LorenzoApiError && error.status === 412
          ? 'The references changed. Check names again.'
          : error instanceof Error
            ? error.message
            : 'The names could not be checked.';
    } finally {
      controls.disabled = false;
    }
  }

  check.addEventListener(
    'click',
    () =>
      void run(async () => {
        results.replaceChildren();
        const draft = sources();
        const stillCurrent = () => {
          const current = sources();
          return current.length === draft.length && current.every((value, i) => value === draft[i]);
        };
        const passages = draft.flatMap(manuscriptPassages).map(nameKey).filter(Boolean);
        if (!passages.length) {
          status.textContent = 'Write a passage first.';
          return;
        }
        status.textContent = 'Checking names…';
        const response = await client.GET(
          '/tenants/{tenant_id}/{source_kind}/{source_id}/references',
          { params: { path } },
        );
        const existing = new Set(
          (await unwrap(response)).filter((ref) => ref.kind === 'beings').map((ref) => ref.id),
        );
        const version = response.response.headers.get('etag');
        if (!version) throw new Error('The Scene references could not be read.');
        const matches = new Map<string, Map<string, Being>>();
        for (let page = 1; panel.isConnected; page++) {
          const found = await unwrap(
            await client.GET('/tenants/{tenant_id}/entities', {
              params: { path: { tenant_id: tenant }, query: { kind: ['being'], page, size: 100 } },
            }),
          );
          for (const entry of found.items) {
            if (!mentioned(passages, entry.name)) continue;
            const key = nameKey(entry.name);
            const group = matches.get(key) ?? new Map<string, Being>();
            group.set(entry.id, entry);
            matches.set(key, group);
          }
          if (page >= found.pages || !found.items.length) break;
        }
        if (!panel.isConnected) return;
        const requireCurrent = () => {
          if (!stillCurrent()) throw new Error('The draft changed. Check names again.');
        };
        requireCurrent();
        for (const group of matches.values()) {
          const entries = Array.from(group.values());
          if (entries.every((entry) => existing.has(entry.id))) continue;
          const entry = entries[0];
          if (entries.length > 1) {
            const note = document.createElement('p');
            note.textContent =
              'Several Beings share the name ' +
              entry.name +
              '. Use the Being lookup to choose one.';
            results.append(note);
            continue;
          }
          const add = document.createElement('button');
          add.type = 'button';
          add.className = 'btn btn-secondary';
          add.textContent = `Add reference to ${entry.name}`;
          add.addEventListener(
            'click',
            () =>
              void run(async () => {
                requireCurrent();
                const current = await unwrap(
                  await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
                    params: { path: { tenant_id: tenant, entity_id: entry.id } },
                  }),
                );
                if (!panel.isConnected) return;
                requireCurrent();
                if (current.name !== entry.name || !current.kinds.includes('being'))
                  throw new Error('The entry changed. Check names again.');
                await unwrap(
                  await client.PUT(
                    '/tenants/{tenant_id}/{source_kind}/{source_id}/references/{kind}/{target_id}',
                    {
                      params: {
                        path: { ...path, kind: 'beings', target_id: entry.id },
                        header: { 'if-match': version },
                      },
                      body: { is_shared: false },
                    },
                  ),
                );
                if (panel.isConnected) await refresh();
              }),
          );
          results.append(add);
        }
        status.textContent = results.childElementCount
          ? 'Choose a name to add a private Scene reference.'
          : 'No new Being references found.';
      }),
  );
  return panel;
}
