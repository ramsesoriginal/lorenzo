import {
  createGraphView,
  type GraphEdge,
  type GraphModel,
  LAYOUT_NAMES,
  type LayoutName,
  LIMITS,
  THEMES,
} from '@lorenzo/graph-renderer';
import { BRANDING_CSS_URL } from './config';
import {
  actions,
  audienceBadge,
  button,
  card,
  claim,
  el,
  empty,
  errorNotice,
  field,
  icon,
  link,
  linkButton,
  loading,
  message,
  metaLine,
  pageHead,
  relationshipHref,
  say,
  sectionHead,
  select,
  statusLine,
  submit,
} from './dom';
import { canManage, libraryName } from './names';
import { notes } from './notes';
import { endPicker, entryPicker, typePicker as findType } from './pickers';
import { start } from './sign-in';
import { readEntry } from './social-api';
import {
  createWeb,
  type Layout,
  listWebs,
  readGraph,
  readWeb,
  saveSettings,
  saveTypes,
  writeMembers,
} from './web-api';
import { audienceWords, directionWords, sentence, stateWords } from './words';

const tenantOf = () => new URLSearchParams(location.search).get('tenant');

/** The icon the brand's atlas has for what an entry is. */
export function iconFor(kinds: readonly string[]): string {
  if (kinds.includes('being')) return 'kind-being';
  if (kinds.includes('location')) return 'kind-location';
  if (kinds.includes('fact')) return 'kind-fact';
  if (kinds.includes('item')) return 'kind-item';
  if (kinds.includes('event')) return 'kind-clock';
  return 'kind-entity';
}

/** The webs of one library, and a form to make one. */
export async function mountWebs() {
  const host = document.querySelector<HTMLElement>('#social-webs');
  if (!host || !claim(host)) return;
  const tenant = tenantOf();
  if (!tenant) {
    location.replace('/');
    return;
  }
  const me = await start();
  if (!me || !host.isConnected) return;
  try {
    host.replaceChildren(loading('Opening the webs…'));
    const [name, manage, first] = await Promise.all([
      libraryName(tenant),
      canManage(tenant),
      listWebs(tenant, 1),
    ]);
    const view = el('div', '', 'stack view');
    view.append(
      pageHead('Webs', {
        crumbs: [link('Libraries', '/')],
        lede: name
          ? `The saved views of the relationships of ${name}.`
          : 'Saved views of relationships.',
      }),
    );
    const list = el('ul', '', 'list');
    list.setAttribute('aria-label', 'Webs');
    for (const web of first.items) {
      const row = el('li');
      const text = el('div', '', 'stack-tight grow');
      const title = el('div', '', 'row-tight');
      title.append(
        icon('kind-social-web'),
        link(web.name, `/web/?${new URLSearchParams({ tenant, id: web.id })}`),
      );
      text.append(title, el('span', `Laid out as ${web.layout}`, 'status-text'));
      row.append(text);
      if (web.is_public !== null && web.is_public !== undefined) {
        row.append(audienceBadge(audienceWords(web.is_public), web.is_public));
      }
      list.append(row);
    }
    const listing = el('section', '', 'stack');
    listing.append(sectionHead('All webs', { count: first.total ?? first.items.length }), list);
    if (first.items.length === 0) listing.append(empty('There are no webs you can see yet.'));
    view.append(listing);

    if (manage) {
      const section = el('section', '', 'stack');
      section.append(sectionHead('Make a web'));
      const form = el('form', '', 'stack');
      form.setAttribute('aria-label', 'Make a web');
      const named = field('Name');
      named.input.required = true;
      const layouts = select(
        'Layout',
        LAYOUT_NAMES.map((l) => [l, l]),
        'circle',
      );
      const visible = field('Everyone in the library may see it', '', 'checkbox');
      const status = statusLine();
      form.append(
        named.label,
        layouts.label,
        visible.label,
        actions(submit('Make the web')),
        status,
      );
      form.addEventListener('submit', (event) => {
        event.preventDefault();
        say(status, 'Making the web…');
        void createWeb(tenant, {
          name: named.input.value.trim(),
          layout: layouts.input.value as Layout,
          is_public: visible.input.checked,
        })
          .then((made) => location.assign(`/web/?${new URLSearchParams({ tenant, id: made.id })}`))
          .catch((error) => say(status, message(error), true));
      });
      section.append(form);
      view.append(section);
    }
    host.replaceChildren(view);
  } catch (error) {
    host.replaceChildren(errorNotice(error));
  }
}

/** One web: the drawing the person may see, its settings, and what it shows. */
export async function mountWeb() {
  const host = document.querySelector<HTMLElement>('#social-web');
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
  let drawing: ReturnType<typeof createGraphView> | null = null;
  // The date lens and "as read by" are the address of the page, unsaved (ADR 0406); a web that saved a
  // lens starts with it when the address names none.
  const lens: { asOf: string | null; asSeenBy: string | null; names: Map<string, string> } = {
    asOf: params.get('as_of'),
    asSeenBy: params.get('as_seen_by'),
    names: new Map(),
  };
  let showOthers = false;
  let first = true;
  const remember = () => {
    const next = new URLSearchParams(location.search);
    for (const [key, value] of [
      ['as_of', lens.asOf],
      ['as_seen_by', lens.asSeenBy],
    ] as const) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    history.replaceState(null, '', `${location.pathname}?${next}`);
  };
  const entryName = async (entry: string) => {
    if (!lens.names.has(entry)) {
      lens.names.set(entry, (await readEntry(tenant, entry).catch(() => null))?.name ?? 'an entry');
    }
    return lens.names.get(entry) as string;
  };
  const draw = async () => {
    drawing?.destroy();
    drawing = null;
    try {
      host.replaceChildren(loading('Opening the web…'));
      const [{ web, version }, manage] = await Promise.all([
        readWeb(tenant, id),
        canManage(tenant),
      ]);
      if (first) {
        first = false;
        if (!lens.asOf && !params.has('as_of')) lens.asOf = web.as_of_event?.id ?? null;
      }
      const graph = await readGraph(tenant, id, lens);
      const asOfName = lens.asOf ? await entryName(lens.asOf) : null;
      const asSeenByName = lens.asSeenBy ? await entryName(lens.asSeenBy) : null;
      const view = el('div', '', 'stack view');
      const meta: Node[] = [metaLine('social', `Laid out as ${web.layout}`)];
      if (web.is_public !== null && web.is_public !== undefined) {
        meta.push(audienceBadge(audienceWords(web.is_public), web.is_public));
      }
      view.append(
        pageHead(web.name, {
          crumbs: [
            link('Libraries', '/'),
            link('Webs', `/webs/?${new URLSearchParams({ tenant })}`),
          ],
          lede: `${graph.members.length} ${graph.members.length === 1 ? 'entry' : 'entries'} and ${graph.edges.length} ${graph.edges.length === 1 ? 'relationship' : 'relationships'}, as you may see them.${asOfName ? ` As of ${asOfName}.` : ''}${asSeenByName ? ` As read by ${asSeenByName}: what it may read, not what it believes.` : ''}`,
          meta,
          actions: [
            linkButton('Open the matrix', `/matrix/?${new URLSearchParams({ tenant, id })}`),
          ],
        }),
      );

      const model: GraphModel = {
        nodes: graph.members.map((m) => ({
          id: m.entry.id,
          name: m.entry.name,
          icon: iconFor(m.entry.kinds),
        })),
        // What has not begun or has ended is not drawn; what is not known is dotted (ADR 0405).
        edges: graph.edges
          .filter((e) => e.as_of !== 'not_yet' && e.as_of !== 'ended')
          .map(
            (e): GraphEdge => ({
              id: e.id,
              a: e.end_a.id,
              b: e.end_b.id,
              directed: e.one_way,
              label: e.name,
              status: e.as_of === 'unknown' ? 'uncertain' : 'direct',
            }),
          ),
      };
      const positions = Object.fromEntries(
        graph.members
          .filter((m) => m.x !== null && m.x !== undefined && m.y !== null && m.y !== undefined)
          .map((m) => [m.entry.id, { x: m.x as number, y: m.y as number }]),
      );

      const stage = card();
      const status = statusLine();
      const tooBig = model.nodes.length > LIMITS.nodes || model.edges.length > LIMITS.edges;
      const hostBox = el('div', '', 'graph-host');
      if (tooBig) {
        stage.body.append(
          empty(
            `A drawing holds at most ${LIMITS.nodes} entries and ${LIMITS.edges} relationships: choose fewer, or limit the web to some types.`,
          ),
        );
      } else if (model.nodes.length === 0) {
        stage.body.append(empty('This web shows no entries yet.'));
      } else {
        stage.body.append(hostBox);
      }
      stage.body.append(status);
      view.append(stage.root);

      // One sentence a relationship: the primary form for reading without sight, kept in step with
      // the selection in the drawing.
      const sentences = el('ul', '', 'list');
      sentences.setAttribute('aria-label', 'Relationships in this web');
      const rows = new Map<string, HTMLElement>();
      const mark = (selected: string | null) => {
        for (const [edgeId, row] of rows) {
          if (edgeId === selected) row.setAttribute('aria-current', 'true');
          else row.removeAttribute('aria-current');
        }
      };
      for (const e of graph.edges) {
        const absent = e.as_of === 'not_yet' || e.as_of === 'ended';
        if (absent && !showOthers) continue;
        const row = el('li');
        const text = el('div', '', 'stack-tight grow');
        const ends = { endA: e.end_a.name, endB: e.end_b.name, oneWay: e.one_way };
        const standing = stateWords(e.as_of);
        text.append(
          link(e.name, relationshipHref(tenant, e.id)),
          el(
            'span',
            `${sentence(ends)}. ${directionWords(ends)}.${standing ? ` ${standing}.` : ''}`,
            'status-text',
          ),
        );
        row.append(text);
        rows.set(e.id, row);
        sentences.append(row);
      }
      const listing = el('section', '', 'stack');
      listing.append(sectionHead('Relationships', { count: graph.edges.length }), sentences);
      if (graph.edges.length === 0)
        listing.append(empty('No relationship ties these entries yet.'));
      if (graph.truncated) {
        listing.append(
          empty('Only the first relationships are shown: limit the web to some types.'),
        );
      }

      // The moved nodes wait for a save.
      const moved = new Map<string, { x: number; y: number }>();
      let current = web.layout as Layout;
      let seed = web.layout_seed;
      let labels = true;
      if (!tooBig && model.nodes.length > 0) {
        drawing = createGraphView(hostBox, {
          model,
          title: web.name,
          iconBase: `${BRANDING_CSS_URL}/icons.svg`,
          themeHint: web.theme_hint ?? null,
          view: { layout: current as LayoutName, seed, positions, labels },
          onSelect: (selection) => {
            mark(selection?.kind === 'edge' ? selection.id : null);
            say(
              status,
              selection
                ? `Selected ${nameOf(model, graph.edges, selection)}.`
                : 'Nothing selected.',
            );
          },
          onOpen: (nodeId) =>
            say(status, `${model.nodes.find((n) => n.id === nodeId)?.name ?? ''} opened.`),
          onMove: (nodeId, at) => {
            moved.set(nodeId, at);
            say(status, `${moved.size} placed by hand, not saved yet.`);
          },
        });
      }

      /** The date lens and the point of view: part of the address, not saved with the web. */
      const lensControls = () => {
        const panel = card();
        panel.body.append(el('h2', 'Date lens and point of view', 'group-title'));
        const events = entryPicker(tenant, 'As of this Event', { kind: 'event' });
        const readers = entryPicker(tenant, 'Read as this entry (what it may read)', {
          kind: 'being',
        });
        const apply = async () => {
          remember();
          await draw();
        };
        const others = field('Also list those that have not begun or have ended', '', 'checkbox');
        others.input.checked = showOthers;
        others.input.addEventListener('change', () => {
          showOthers = others.input.checked;
          void draw();
        });
        panel.body.append(
          events.label,
          actions(
            button('Read as of this Event', async () => {
              const picked = events.value();
              if (!picked) throw new Error('Choose an Event first.');
              lens.asOf = picked;
              lens.names.set(picked, events.name());
              await apply();
            }),
            button('Remove the date lens', async () => {
              lens.asOf = null;
              await apply();
            }),
          ),
          ...(lens.asOf ? [others.label] : []),
          readers.label,
          actions(
            button('Read as this entry', async () => {
              const picked = readers.value();
              if (!picked) throw new Error('Choose an entry first.');
              lens.asSeenBy = picked;
              lens.names.set(picked, readers.name());
              await apply();
            }),
            button('Read as myself', async () => {
              lens.asSeenBy = null;
              await apply();
            }),
          ),
        );
        return panel.root;
      };

      const controls = card();
      controls.body.append(el('h2', 'How it is drawn', 'group-title'));
      const layout = select(
        'Layout',
        LAYOUT_NAMES.map((l) => [l, l]),
        current,
      );
      const seeded = field('Seed', String(seed), 'number');
      const themes = select(
        'Theme',
        [
          ['', 'The web2019s own'],
          ...Object.keys(THEMES).map((t): [string, string] => [
            t,
            t === 'family' ? 'Family tree' : 'Default',
          ]),
        ],
        '',
      );
      themes.input.addEventListener('change', () => drawing?.setTheme(themes.input.value || null));
      const named = field('Show the labels', '', 'checkbox');
      named.input.checked = labels;
      layout.input.addEventListener('change', () => {
        current = layout.input.value as Layout;
        drawing?.setView({ layout: current as LayoutName });
      });
      seeded.input.addEventListener('change', () => {
        seed = Math.max(0, Math.floor(Number(seeded.input.value) || 0));
        drawing?.setView({ seed });
      });
      named.input.addEventListener('change', () => {
        labels = named.input.checked;
        drawing?.setView({ labels });
      });
      const zoom = actions(
        button('Zoom in', () => drawing?.zoomIn()),
        button('Zoom out', () => drawing?.zoomOut()),
      );
      controls.body.append(layout.label, seeded.label, themes.label, named.label, zoom);
      if (manage) {
        const state = { version };
        controls.body.append(
          actions(
            button('Save how it is drawn', async () => {
              const saved = await saveSettings(tenant, id, state.version, {
                layout: current,
                layout_seed: seed,
                theme_hint: themes.input.value || web.theme_hint || null,
                view: web.view ?? null,
                standing_stat_id: web.standing_stat_id ?? null,
                as_of_event: lens.asOf,
              });
              state.version = saved.version;
              say(status, 'Saved how it is drawn.');
            }),
            button('Save hand placements', async () => {
              if (moved.size === 0) {
                say(status, 'Nothing was placed by hand.');
                return;
              }
              const saved = await writeMembers(tenant, id, state.version, {
                set: [...moved].map(([entry, at]) => ({ entry_id: entry, x: at.x, y: at.y })),
              });
              state.version = saved.version;
              moved.clear();
              say(status, 'Saved the hand placements.');
            }),
          ),
        );
      }
      view.append(controls.root, lensControls(), listing);
      view.append(notes(tenant, id));

      if (manage) view.append(editor(tenant, id, version, graph, web, draw));
      host.replaceChildren(view);
    } catch (error) {
      host.replaceChildren(errorNotice(error));
    }
  };
  await draw();
}

function nameOf(
  model: GraphModel,
  edges: readonly { id: string; name: string }[],
  selection: { kind: 'node' | 'edge'; id: string },
): string {
  return selection.kind === 'node'
    ? (model.nodes.find((n) => n.id === selection.id)?.name ?? '')
    : (edges.find((e) => e.id === selection.id)?.name ?? '');
}

/** What a writer changes about what the web shows: its members, and the types it is limited to. */
function editor(
  tenant: string,
  id: string,
  version: string,
  graph: Awaited<ReturnType<typeof readGraph>>,
  web: Awaited<ReturnType<typeof readWeb>>['web'],
  redraw: () => Promise<void>,
) {
  const section = el('section', '', 'stack');
  section.append(sectionHead('What it shows'));
  const status = statusLine();

  const members = card();
  members.body.append(el('h2', 'Entries', 'group-title'));
  const list = el('ul', '', 'list');
  list.setAttribute('aria-label', 'Entries in this web');
  for (const m of graph.members) {
    const row = el('li');
    row.append(
      el('span', m.entry.name, 'grow'),
      button(`Take out ${m.entry.name}`, async () => {
        await writeMembers(tenant, id, version, { remove: [m.entry.id] });
        await redraw();
      }),
    );
    list.append(row);
  }
  members.body.append(list);
  const picker = endPicker(tenant, 'Add an entry');
  members.body.append(
    picker.label,
    actions(
      button('Add it to the web', async () => {
        const entry = picker.value();
        if (!entry) throw new Error('Choose an entry first.');
        await writeMembers(tenant, id, version, { set: [{ entry_id: entry }] });
        await redraw();
      }),
    ),
  );

  const types = card();
  types.body.append(el('h2', 'Types of relationship', 'group-title'));
  types.body.append(
    el(
      'p',
      web.types.length
        ? `Only relationships of these types are drawn: ${web.types.map((t) => t.name).join(', ')}.`
        : 'Every type of relationship is drawn.',
      'status-text',
    ),
  );
  const typeList = el('ul', '', 'list');
  typeList.setAttribute('aria-label', 'Types this web is limited to');
  const current = web.types.map((t) => t.id);
  for (const t of web.types) {
    const row = el('li');
    row.append(
      el('span', t.name, 'grow'),
      button(`Stop limiting to ${t.name}`, async () => {
        await saveTypes(
          tenant,
          id,
          version,
          current.filter((x) => x !== t.id),
        );
        await redraw();
      }),
    );
    typeList.append(row);
  }
  const typePicker = findType(tenant, 'Limit to a type');
  types.body.append(
    typeList,
    typePicker.label,
    actions(
      button('Limit to it', async () => {
        const type = typePicker.value();
        if (!type) throw new Error('Choose a type first.');
        await saveTypes(tenant, id, version, [...new Set([...current, type])]);
        await redraw();
      }),
    ),
  );
  section.append(members.root, types.root, status);
  return section;
}
