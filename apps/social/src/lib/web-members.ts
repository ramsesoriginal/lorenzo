import { client, fetchAllPages, unwrap } from './api';
import { panelDialog } from './dialog';
import { actions, button, el, errorNotice, say, select, statusLine } from './dom';
import { endPicker, entryPicker } from './pickers';
import type { EntryChoice } from './social-api';
import { readGraph, readWeb, writeMembers } from './web-api';

export interface Person {
  id: string;
  name: string;
}

/** The most entries one step of "within some steps" adds at a time. */
const MOST = 100;

/** Every entry the relationships of the library tie to these, one step out. */
async function neighbours(tenant: string, from: readonly string[]): Promise<Person[]> {
  const found = new Map<string, Person>();
  for (const id of from) {
    const rows = await fetchAllPages(async (page) =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/relationships', {
          params: { path: { tenant_id: tenant }, query: { end: id, page, size: 100 } },
          cache: 'no-cache',
        }),
      ),
    );
    for (const r of rows) {
      for (const end of [r.end_a, r.end_b]) {
        if (end.id !== id) found.set(end.id, { id: end.id, name: end.name });
      }
    }
  }
  return [...found.values()];
}

async function findGroups(tenant: string, query: string): Promise<EntryChoice[]> {
  const needle = query.toLowerCase();
  const groups = await fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/groups', {
        params: { path: { tenant_id: tenant }, query: { page, size: 100 } },
        cache: 'no-cache',
      }),
    ),
  );
  return groups
    .filter((g) => g.name.toLowerCase().includes(needle))
    .slice(0, 12)
    .map((g) => ({ id: g.id, name: g.name, kinds: [] }));
}

/**
 * The Members control (SO6): add entries by name, a group's members, or everyone within some steps
 * of the selected entry, and take members out. It writes explicit rows and never a rule, each under
 * the version the web has now.
 */
export function openMembers(options: {
  tenant: string;
  id: string;
  selected: Person | null;
  changed(): Promise<void>;
}) {
  const { tenant, id } = options;
  let members: Person[] = [];
  const status = statusLine();
  const list = el('ul', '', 'list');
  list.setAttribute('aria-label', 'Entries in this web');

  const reload = async () => {
    members = (await readGraph(tenant, id)).members.map((m) => ({
      id: m.entry.id,
      name: m.entry.name,
    }));
    list.replaceChildren();
    for (const m of members) {
      const row = el('li');
      row.append(
        el('span', m.name, 'grow'),
        button(`Take out ${m.name}`, async () => {
          await write({ remove: [m.id] }, `Took out ${m.name}.`);
        }),
      );
      list.append(row);
    }
    if (members.length === 0) list.append(el('li', 'This web has no entries yet.', 'status-text'));
  };
  const write = async (body: { set?: { entry_id: string }[]; remove?: string[] }, said: string) => {
    const { version } = await readWeb(tenant, id);
    await writeMembers(tenant, id, version, body);
    await reload();
    say(status, said);
    await options.changed();
  };
  const addAll = async (people: Person[], words: string) => {
    const have = new Set(members.map((m) => m.id));
    const fresh = people.filter((p) => !have.has(p.id)).slice(0, MOST);
    if (fresh.length === 0) {
      say(status, 'They are all in the web already.');
      return;
    }
    await write(
      { set: fresh.map((p) => ({ entry_id: p.id })) },
      `${words}: added ${fresh.length}.${people.length - have.size > MOST ? ` Only the first ${MOST} were added.` : ''}`,
    );
  };

  // By name.
  const byName = endPicker(tenant, 'Add an entry');
  const nameBox = el('section', '', 'stack-tight');
  nameBox.append(
    el('h3', 'By name', 'group-title'),
    byName.label,
    actions(
      button('Add it to the web', async () => {
        const entry = byName.value();
        if (!entry) throw new Error('Choose an entry first.');
        await addAll([{ id: entry, name: byName.name() }], byName.name());
      }),
    ),
  );

  // A group's members.
  const group = entryPicker(tenant, 'Add the members of a group', {
    find: findGroups,
    nothing: 'No group by that name.',
  });
  const groupBox = el('section', '', 'stack-tight');
  groupBox.append(
    el('h3', 'A group’s members', 'group-title'),
    group.label,
    actions(
      button('Add its members', async () => {
        const picked = group.value();
        if (!picked) throw new Error('Choose a group first.');
        const rows = await unwrap(
          await client.GET('/tenants/{tenant_id}/groups/{group_entity_id}/members', {
            params: { path: { tenant_id: tenant, group_entity_id: picked } },
            cache: 'no-cache',
          }),
        );
        await addAll(
          rows.map((r) => ({ id: r.id, name: r.name })),
          `Members of ${group.name()}`,
        );
      }),
    ),
  );

  // Within some steps of the selected entry.
  const steps = select('Steps', [
    ['1', 'One step'],
    ['2', 'Two steps'],
    ['3', 'Three steps'],
  ]);
  const near = el('section', '', 'stack-tight');
  near.append(el('h3', 'Everyone within some steps', 'group-title'));
  if (options.selected) {
    const around = options.selected;
    near.append(
      el('p', `Counted from ${around.name}, the selected entry.`, 'status-text'),
      steps.label,
      actions(
        button(`Add everyone near ${around.name}`, async () => {
          let reached = new Map<string, Person>([[around.id, around]]);
          let edge: Person[] = [around];
          for (let step = 0; step < Number(steps.input.value); step += 1) {
            const next = await neighbours(
              tenant,
              edge.map((p) => p.id),
            );
            edge = next.filter((p) => !reached.has(p.id));
            reached = new Map([...reached, ...edge.map((p) => [p.id, p] as const)]);
          }
          reached.delete(around.id);
          await addAll([...reached.values()], `Within ${steps.input.value} of ${around.name}`);
        }),
      ),
    );
  } else {
    near.append(el('p', 'Select an entry in the drawing first, and count from it.', 'status-text'));
  }

  const removing = el('section', '', 'stack-tight');
  removing.append(el('h3', 'In this web', 'group-title'), list);
  const dialog = panelDialog('Members', [nameBox, groupBox, near, removing, status]);
  reload().catch((error) => list.replaceChildren(errorNotice(error)));
  return dialog;
}
