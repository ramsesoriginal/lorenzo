import type { components } from '@lorenzo/api-client';
import { client, LorenzoApiError, unwrap } from './api';
import { manuscriptPassages } from './manuscript-count';
import { mentioned, nameKey } from './mentioned-names';

type Period = components['schemas']['PeriodDetailOut'];

export function suggestedPeriods(
  tenant: string,
  scene: string,
  sources: () => string[],
  refresh: () => Promise<void>,
) {
  const panel = document.createElement('details');
  const summary = document.createElement('summary');
  summary.textContent = 'Suggested period';
  const controls = document.createElement('fieldset');
  const legend = document.createElement('legend');
  legend.textContent = 'Dates in this Scene';
  const check = document.createElement('button');
  check.type = 'button';
  check.className = 'btn btn-secondary';
  check.textContent = 'Check dates';
  const results = document.createElement('div');
  results.className = 'stack-tight';
  const status = document.createElement('p');
  status.setAttribute('role', 'status');
  const hint = document.createElement('p');
  hint.textContent = 'Looks for the full names of existing calendar periods in your prose.';
  controls.append(legend, hint, check, results);
  panel.append(summary, controls, status);
  const path = { tenant_id: tenant, scene_id: scene };

  async function run(operation: () => Promise<void>) {
    if (controls.disabled) return;
    controls.disabled = true;
    try {
      await operation();
    } catch (error) {
      results.replaceChildren();
      status.textContent =
        error instanceof LorenzoApiError && error.status === 412
          ? 'The Scene changed. Check dates again.'
          : error instanceof Error
            ? error.message
            : 'The dates could not be checked.';
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
        const requireCurrent = () => {
          const current = sources();
          if (current.length !== draft.length || current.some((value, i) => value !== draft[i]))
            throw new Error('The draft changed. Check dates again.');
        };
        const passages = draft.flatMap(manuscriptPassages).map(nameKey).filter(Boolean);
        if (!passages.length) {
          status.textContent = 'Write a passage first.';
          return;
        }
        status.textContent = 'Checking dates…';
        const response = await client.GET('/tenants/{tenant_id}/scenes/{scene_id}', {
          params: { path },
        });
        const currentScene = await unwrap(response);
        if (currentScene.period_entity_id) {
          status.textContent = 'This Scene already has a period. Use Period to change it.';
          return;
        }
        const version = response.response.headers.get('etag');
        if (!version) throw new Error('The Scene could not be read.');
        const matches = new Map<string, Map<string, Period>>();
        for (let page = 1; panel.isConnected; page++) {
          const found = await unwrap(
            await client.GET('/tenants/{tenant_id}/calendar-periods', {
              params: { path: { tenant_id: tenant }, query: { page, size: 100 } },
            }),
          );
          for (const entry of found.items) {
            if (!mentioned(passages, entry.name)) continue;
            const key = nameKey(entry.name);
            const group = matches.get(key) ?? new Map<string, Period>();
            group.set(entry.entity_id, entry);
            matches.set(key, group);
          }
          if (page >= found.pages || !found.items.length) break;
        }
        if (!panel.isConnected) return;
        requireCurrent();
        for (const group of matches.values()) {
          const entries = Array.from(group.values());
          const entry = entries[0];
          if (entries.length > 1) {
            const note = document.createElement('p');
            note.textContent =
              'Several periods share the name ' +
              entry.name +
              '. Use the Period lookup to choose one.';
            results.append(note);
            continue;
          }
          const add = document.createElement('button');
          add.type = 'button';
          add.className = 'btn btn-secondary';
          add.textContent = `Set period to ${entry.name} (${entry.calendar_name})`;
          add.addEventListener(
            'click',
            () =>
              void run(async () => {
                requireCurrent();
                const found = await unwrap(
                  await client.GET('/tenants/{tenant_id}/calendar-periods', {
                    params: {
                      path: { tenant_id: tenant },
                      query: { id: [entry.entity_id], size: 1 },
                    },
                  }),
                );
                if (!panel.isConnected) return;
                requireCurrent();
                const current = found.items[0];
                if (
                  !current ||
                  current.entity_id !== entry.entity_id ||
                  current.name !== entry.name ||
                  current.calendar_entity_id !== entry.calendar_entity_id ||
                  current.calendar_name !== entry.calendar_name ||
                  current.year !== entry.year ||
                  current.segment !== entry.segment ||
                  current.day !== entry.day ||
                  current.granularity !== entry.granularity
                )
                  throw new Error('The period changed or is unavailable. Check dates again.');
                await unwrap(
                  await client.PATCH('/tenants/{tenant_id}/scenes/{scene_id}', {
                    params: { path, header: { 'if-match': version } },
                    body: { period_entity_id: entry.entity_id },
                  }),
                );
                if (panel.isConnected) await refresh();
              }),
          );
          results.append(add);
        }
        status.textContent = results.childElementCount
          ? 'Choose the period for this Scene.'
          : 'No matching calendar periods found.';
      }),
  );
  return panel;
}
