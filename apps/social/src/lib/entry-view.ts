import { client, fetchAllPages, unwrap } from './api';
import {
  audienceBadge,
  claim,
  el,
  empty,
  entryHref,
  errorNotice,
  icon,
  link,
  loading,
  message,
  metaLine,
  pageHead,
  relationshipHref,
  say,
  sectionHead,
  select,
  statusLine,
} from './dom';
import { parseInput } from './matrix';
import { limitsOf, listStats, readStanding, type StatDef } from './matrix-api';
import { libraryName } from './names';
import { start } from './sign-in';
import { type listRelationships, readEntry } from './social-api';
import { standingMark } from './standing';
import { listTypes, setStatValue } from './types-api';
import { audienceWords } from './words';

type Row = Awaited<ReturnType<typeof listRelationships>>['items'][number];

/** Every relationship that has the entry as an end, optionally of one type. */
async function around(tenant: string, id: string, type?: string): Promise<Row[]> {
  return fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/relationships', {
        params: {
          path: { tenant_id: tenant },
          query: { end: id, page, size: 100, ...(type ? { type } : {}) },
        },
        cache: 'no-cache',
      }),
    ),
  );
}

/**
 * An entry's own social page: its relationships grouped by type, each with the other end, which way it
 * goes and its standing (written in place by those who may), and, for a group, its members apart.
 */
export async function mountEntry() {
  const host = document.querySelector<HTMLElement>('#social-entry');
  if (!host || !claim(host)) return;
  const params = new URLSearchParams(location.search);
  const tenant = params.get('tenant');
  const id = params.get('id');
  if (!tenant || !id) {
    location.replace('/');
    return;
  }
  const me = await start();
  if (!me || !host.isConnected) return;
  try {
    host.replaceChildren(loading('Opening the entry…'));
    const [entry, name, stats, types, all, members] = await Promise.all([
      readEntry(tenant, id),
      libraryName(tenant),
      listStats(tenant),
      listTypes(tenant),
      around(tenant, id),
      unwrap(
        await client.GET('/tenants/{tenant_id}/groups/{group_entity_id}/members', {
          params: { path: { tenant_id: tenant, group_entity_id: id } },
          cache: 'no-cache',
        }),
      ).catch(() => []),
    ]);
    const numbers = stats.filter((s) => s.value_type === 'int');
    let stat: StatDef | undefined = numbers[0];
    let values = stat ? await readStanding(tenant, stat.id) : new Map();

    const view = el('div', '', 'stack view');
    view.append(
      pageHead(entry.name, {
        crumbs: [link('Relationships', `/relationships/?${new URLSearchParams({ tenant })}`)],
        lede: name
          ? `${entry.name}’s relationships in ${name}, as you may see them.`
          : 'Its relationships, as you may see them.',
        meta: [
          metaLine(
            'kind-relationship',
            `${all.length} ${all.length === 1 ? 'relationship' : 'relationships'}`,
          ),
        ],
      }),
    );

    const status = statusLine();
    const body = el('div', '', 'stack');
    const standingSelect = select(
      'Standing',
      numbers.map((s) => [s.id, s.name]),
      stat?.id ?? '',
    );
    standingSelect.input.addEventListener('change', () => {
      stat = numbers.find((s) => s.id === standingSelect.input.value);
      void (async () => {
        values = stat ? await readStanding(tenant, stat.id) : new Map();
        draw();
      })();
    });

    const one = (row: Row) => {
      const other = row.end_a.id === id ? row.end_b : row.end_a;
      const way = !row.one_way ? 'With' : row.end_a.id === id ? 'To' : 'From';
      const item = el('li');
      const text = el('div', '', 'stack-tight grow');
      const title = el('div', '', 'row-tight');
      title.append(
        icon('kind-relationship'),
        el('span', way, 'chip'),
        link(other.name, entryHref(tenant, other.id)),
      );
      text.append(title, link(row.name, relationshipHref(tenant, row.id)));
      item.append(text);
      if (row.is_public !== null && row.is_public !== undefined) {
        item.append(audienceBadge(audienceWords(row.is_public), row.is_public));
      }
      if (stat) {
        const current = values.get(row.id);
        if (row.can_manage || row.can_edit) {
          const input = el('input', '', 'text-input matrix-input');
          input.inputMode = 'numeric';
          input.setAttribute('aria-label', `${stat.name} of ${row.name}`);
          input.value = current ? String(current.value) : '';
          const limits = limitsOf(stat);
          const statId = stat.id;
          input.addEventListener('change', () => {
            const parsed = parseInput(input.value, limits);
            if (!parsed.ok) {
              say(status, parsed.reason, true);
              return;
            }
            if (parsed.value === null) {
              say(
                status,
                'A standing is changed here, not cleared: use the matrix to clear it.',
                true,
              );
              return;
            }
            say(status, 'Saving…');
            void setStatValue(tenant, row.id, statId, parsed.value)
              .then(async () => {
                values = await readStanding(tenant, statId);
                say(status, `Saved ${limits.name} of ${row.name}.`);
              })
              .catch((error) => say(status, message(error), true));
          });
          item.append(input);
        } else if (current && typeof current.value === 'number') {
          item.append(
            standingMark(
              current.value,
              { min: stat.min_value ?? null, max: stat.max_value ?? null },
              current.own ? 'direct' : 'inherited',
            ),
          );
        }
      }
      return item;
    };

    const draw = () => {
      body.replaceChildren();
      if (all.length === 0) {
        body.append(empty('No relationship you can see has this entry as an end.'));
        return;
      }
      const placed = new Set<string>();
      for (const type of types) {
        const rows = grouped.get(type.id) ?? [];
        if (rows.length === 0) continue;
        for (const r of rows) placed.add(r.id);
        body.append(section(type.name, rows));
      }
      const rest = all.filter((r) => !placed.has(r.id));
      if (rest.length) body.append(section('Without a type', rest));
    };
    const section = (title: string, rows: Row[]) => {
      const box = el('section', '', 'stack');
      const list = el('ul', '', 'list');
      list.setAttribute('aria-label', title);
      for (const r of rows) list.append(one(r));
      box.append(sectionHead(title, { count: rows.length }), list);
      return box;
    };

    // The relationships of each type the library has, read type by type.
    const grouped = new Map<string, Row[]>();
    if (all.length) {
      await Promise.all(
        types.map(async (type) => {
          const rows = await around(tenant, id, type.id);
          if (rows.length) grouped.set(type.id, rows);
        }),
      );
    }
    draw();

    if (numbers.length) view.append(standingSelect.label);
    view.append(body, status);

    if (members.length) {
      const box = el('section', '', 'stack');
      const list = el('ul', '', 'list');
      list.setAttribute('aria-label', 'Members');
      for (const m of members) {
        const row = el('li');
        row.append(icon('kind-being'), link(m.name, entryHref(tenant, m.id)));
        list.append(row);
      }
      box.append(sectionHead('Members', { count: members.length }), list);
      view.append(box);
    }
    host.replaceChildren(view);
  } catch (error) {
    host.replaceChildren(errorNotice(error));
  }
}
