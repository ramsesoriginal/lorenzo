// The Distance section of a Map page (ADR 0368): how far one place drawn on the Map is from another,
// by the straight line on this Map and, when a stat is chosen, by the connections. It says what the
// API answered, in words, and draws nothing on the sheet.
import { client, fetchAllPages, type Schema, unwrap } from './api';
import { type Answer, legWords, routeWords, straightWords } from './distance-words';
import { actions, el, empty, message, say, sectionHead, select, statusLine, submit } from './dom';

type Place = { id: string; name: string };

type Stat = { id: string; name: string; unit: string | null };

const NUMBERS = new Set(['int', 'float']);

async function numberStats(tenant: string): Promise<Stat[]> {
  const all = await fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/stat-definitions', {
        params: { path: { tenant_id: tenant }, query: { page, size: 100 } },
        cache: 'no-cache',
      }),
    ),
  );

  return all
    .filter((stat: Schema<'StatDefinitionOut'>) => NUMBERS.has(stat.value_type))
    .map((stat: Schema<'StatDefinitionOut'>) => ({
      id: stat.id,
      name: stat.name,
      unit: stat.unit ?? null,
    }));
}

async function ask(
  tenant: string,
  map: string,
  from: string,
  to: string,
  mode: 'route' | 'straight',
  measure?: string,
): Promise<Answer> {
  return (await unwrap(
    await client.GET('/tenants/{tenant_id}/distance', {
      params: {
        path: { tenant_id: tenant },
        query: { from, to, mode, ...(mode === 'straight' ? { map } : { measure }) },
      },
      cache: 'no-cache',
    }),
  )) as Answer;
}

export function distanceSection(context: {
  tenant: string;
  map: { id: string; system: Record<string, unknown> };
  places: readonly Place[];
}) {
  const { tenant, map, places } = context;
  const section = el('section', '', 'stack');
  section.append(sectionHead('Distance'));
  if (places.length < 2) {
    section.append(empty('Draw two places on this Map to measure between them.'));
    return section;
  }
  const sorted = [...places].sort((a, b) => a.name.localeCompare(b.name) || (a.id < b.id ? -1 : 1));
  const choices = (): [string, string][] => [
    ['', 'Choose a place…'],
    ...sorted.map((place): [string, string] => [place.id, place.name]),
  ];
  const from = select('Measure from', choices());
  const to = select('Measure to', choices());
  const stat = select('By the connections, measured in', [['', 'Not by the connections']]);
  const result = el('div', '', 'stack-tight');
  result.setAttribute('role', 'status');
  const status = statusLine();
  const form = el('form', '', 'stack-tight');
  const row = el('div', '', 'grid');
  row.style.setProperty('--grid-min', '200px');
  row.append(from.label, to.label, stat.label);
  form.append(row, actions(submit('Measure', 'secondary')), status, result);
  section.append(form);

  let stats: Stat[] = [];
  void numberStats(tenant)
    .then((found) => {
      stats = found;
      stat.input.replaceChildren(
        ...[
          ['', 'Not by the connections'],
          ...found.map((s): [string, string] => [s.id, s.unit ? `${s.name} (${s.unit})` : s.name]),
        ].map(([id, title]) => {
          const option = el('option', title);
          option.value = id ?? '';
          return option;
        }),
      );
    })
    .catch(() => {
      // Only the straight line is on offer when the stats cannot be read.
    });

  const metric = ['square', 'rect'].includes(String(map.system.kind))
    ? (map.system.metric as string | undefined)
    : undefined;
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    if (!from.input.value || !to.input.value) {
      say(status, 'Choose the two places to measure between.', true);
      return;
    }
    status.textContent = '';
    void (async () => {
      try {
        const lines: HTMLElement[] = [];
        const straight = await ask(tenant, map.id, from.input.value, to.input.value, 'straight');
        lines.push(el('p', straightWords(straight, metric), 'status-text'));
        if (stat.input.value) {
          const route = await ask(
            tenant,
            map.id,
            from.input.value,
            to.input.value,
            'route',
            stat.input.value,
          );
          lines.push(el('p', routeWords(route), 'status-text'));
          if (route.route.length) {
            const unit = stats.find((s) => s.id === stat.input.value)?.unit ?? route.unit;
            const list = el('ol', '', 'list map-route');
            for (const leg of route.route) list.append(el('li', legWords(leg, unit)));
            lines.push(list);
          }
        }
        result.replaceChildren(...lines);
      } catch (error) {
        result.replaceChildren();
        say(status, message(error), true);
      }
    })();
  });
  return section;
}
