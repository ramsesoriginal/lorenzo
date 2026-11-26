import {
  createGraphView,
  type GraphEdge,
  type GraphGroup,
  type GraphModel,
  LAYOUT_NAMES,
  type LayoutName,
  LIMITS,
  THEMES,
} from '@lorenzo/graph-renderer';
import { BRANDING_CSS_URL } from './config';
import { formDialog } from './dialog';
import {
  actions,
  audienceBadge,
  button,
  card,
  claim,
  el,
  empty,
  entryHref,
  errorNotice,
  field,
  icon,
  link,
  loading,
  metaLine,
  relationshipHref,
  say,
  sectionHead,
  select,
  statusLine,
} from './dom';
import { eventChooser } from './event-chooser';
import { listStats, readStanding, type StatDef } from './matrix-api';
import { canManage } from './names';
import { notes } from './notes';
import { entryPicker, typePicker as findType } from './pickers';
import { relationshipForm } from './relationship-form';
import { shellOf, start } from './sign-in';
import { readEntry } from './social-api';
import { type Layout, readGraph, readWeb, saveSettings, saveTypes, writeMembers } from './web-api';
import { edgeFacts, loadGroups } from './web-facts';
import { openMembers } from './web-members';
import { membersPanel, relationshipPanel } from './web-panel';
import { rememberWeb } from './webs-view';
import { audienceWords, directionWords, sentence, stateWords } from './words';

/** The icon the brand's atlas has for what an entry is. */
export function iconFor(kinds: readonly string[]): string {
  if (kinds.includes('being')) return 'kind-being';
  if (kinds.includes('location')) return 'kind-location';
  if (kinds.includes('fact')) return 'kind-fact';
  if (kinds.includes('item')) return 'kind-item';
  if (kinds.includes('event')) return 'kind-clock';
  return 'kind-entity';
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
  rememberWeb(tenant, id);
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
  // The tab the panel shows stays open when the web is drawn again.
  let panelTab: string | null = null;
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
      const view = el('div', '', 'web-workspace');
      view.dataset.fitWindow = '';
      view.dataset.panel = 'closed';
      const stageBox = el('div', '', 'web-stage');
      const floatHead = el('div', '', 'web-float web-float--head');
      const floatBar = el('div', '', 'web-float web-float--bar');
      const floatZoom = el('div', '', 'web-float web-float--zoom');
      const floatLegend = el('div', '', 'web-float web-float--legend');
      const panel = el('aside', '', 'web-panel card');
      panel.setAttribute('aria-label', 'The web’s panel');
      panel.hidden = true;
      view.append(stageBox, floatHead, floatBar, floatZoom, floatLegend, panel);

      const counts = `${graph.members.length} ${graph.members.length === 1 ? 'entry' : 'entries'} and ${graph.edges.length} ${graph.edges.length === 1 ? 'relationship' : 'relationships'}, as you may see them.`;
      const title = card();
      title.root.classList.add('web-title-card');
      const crumb = link('Webs', `/webs/?${new URLSearchParams({ tenant })}`);
      const titleRow = el('div', '', 'row-tight');
      titleRow.append(crumb);
      const heading = el('h1', web.name, 'web-title');
      const metaRow = el('div', '', 'row-tight');
      metaRow.append(metaLine('social', `Laid out as ${web.layout}`));
      if (web.is_public !== null && web.is_public !== undefined) {
        metaRow.append(audienceBadge(audienceWords(web.is_public), web.is_public));
      }
      title.body.append(titleRow, heading, el('p', counts, 'status-text'), metaRow);
      floatHead.append(title.root);

      // What a lens has on is said, and cleared, in one line (SO4).
      const lensLine = (text: string, clearName: string, clear: () => void) => {
        const line = el('div', '', 'lens-line');
        line.append(
          el('span', text),
          button(
            clearName,
            async () => {
              clear();
              remember();
              await draw();
            },
            { variant: 'secondary' },
          ),
        );
        floatHead.append(line);
      };
      if (asOfName) {
        lensLine(`Looking as of ${asOfName}`, 'Clear the date lens', () => {
          lens.asOf = null;
        });
      }
      if (asSeenByName) {
        lensLine(
          `As read by ${asSeenByName}: what it may read, not what it believes`,
          'Clear the reader',
          () => {
            lens.asSeenBy = null;
          },
        );
      }
      // What the date lens leaves out is counted, with a switch that lists it (SO4).
      const absent = graph.edges.filter((e) => e.as_of === 'not_yet' || e.as_of === 'ended').length;
      if (lens.asOf && absent > 0) {
        const count = el('div', '', 'lens-line');
        const listThem = button(
          showOthers ? 'Stop listing them' : 'List them',
          async () => {
            showOthers = !showOthers;
            await draw();
          },
          { variant: 'secondary' },
        );
        listThem.setAttribute('aria-pressed', String(showOthers));
        count.append(
          el(
            'span',
            `${absent} ${absent === 1 ? 'relationship has' : 'relationships have'} not begun or ${absent === 1 ? 'has' : 'have'} ended, and ${absent === 1 ? 'is' : 'are'} ${showOthers ? 'shown faded' : 'not drawn'}`,
          ),
          listThem,
        );
        floatHead.append(count);
      }

      const facts = await edgeFacts(
        tenant,
        graph.members.map((m) => m.entry.id),
        graph.edges,
      );
      // The standing a web shows: drawn as the line's weight on the stat's scale, and said in its label.
      const stats = await listStats(tenant).catch((): StatDef[] => []);
      const numbers = stats.filter((x) => x.value_type === 'int');
      const shown = numbers.find((x) => x.id === web.standing_stat_id);
      const standings = shown
        ? await readStanding(tenant, shown.id).catch(() => new Map<string, { value: unknown }>())
        : new Map<string, { value: unknown }>();
      const scale: readonly [number, number] | undefined =
        shown && shown.min_value != null && shown.max_value != null
          ? [shown.min_value, shown.max_value]
          : undefined;
      const model: GraphModel = {
        nodes: graph.members.map((m) => ({
          id: m.entry.id,
          name: m.entry.name,
          icon: iconFor(m.entry.kinds),
        })),
        // What has not begun or has ended is not drawn; what is not known is dotted (ADR 0405).
        // Those the lens leaves out are drawn only when asked for, and then faded (SO4).
        edges: graph.edges
          .filter((e) => showOthers || (e.as_of !== 'not_yet' && e.as_of !== 'ended'))
          .map(
            (e): GraphEdge => ({
              id: e.id,
              a: e.end_a.id,
              b: e.end_b.id,
              directed: e.one_way,
              // The type and the standing label a line; a relationship with no type reads as its name.
              label: (() => {
                const v = standings.get(e.id)?.value;
                const said = facts.typeOf.get(e.id) ?? e.name;
                return typeof v === 'number' ? `${said}: ${v}` : said;
              })(),
              // Solid is stated, dashed holds through others, dotted is not known (identity section 18).
              status:
                e.as_of === 'unknown'
                  ? 'uncertain'
                  : facts.through.has(e.id)
                    ? 'derived'
                    : 'direct',
              ...(e.as_of === 'not_yet' || e.as_of === 'ended' ? { dim: true } : {}),
              ...(() => {
                const v = standings.get(e.id)?.value;
                return typeof v === 'number' && scale ? { value: v, scale } : {};
              })(),
            }),
          ),
      };
      const positions = Object.fromEntries(
        graph.members
          .filter((m) => m.x !== null && m.x !== undefined && m.y !== null && m.y !== undefined)
          .map((m) => [m.entry.id, { x: m.x as number, y: m.y as number }]),
      );

      const status = statusLine();
      const tooBig = model.nodes.length > LIMITS.nodes || model.edges.length > LIMITS.edges;
      const hostBox = el('div', '', 'graph-host');
      const graphPane = el('div', '', 'web-pane web-pane--graph');
      const listPane = el('div', '', 'web-pane web-pane--list');
      const matrixPane = el('div', '', 'web-pane web-pane--matrix');
      if (tooBig) {
        graphPane.append(
          empty(
            `A drawing holds at most ${LIMITS.nodes} entries and ${LIMITS.edges} relationships: choose fewer, or limit the web to some types.`,
          ),
        );
      } else if (model.nodes.length === 0) {
        graphPane.append(empty('This web shows no entries yet.'));
      } else {
        graphPane.append(hostBox);
      }
      stageBox.append(graphPane, listPane, matrixPane);
      floatLegend.append(status);

      // One sentence a relationship: the primary form for reading without sight, kept in step with
      // the selection in the drawing.
      const sentences = el('ul', '', 'list');
      sentences.setAttribute('aria-label', 'Relationships in this web');
      // Choosing from the list is choosing in the drawing: the same selection, the same panel.
      let pick: (choice: { kind: 'node' | 'edge'; id: string }) => void = () => {};
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
        const standing =
          e.as_of === 'unknown' && asOfName ? `Unknown as of ${asOfName}` : stateWords(e.as_of);
        text.append(
          link(e.name, relationshipHref(tenant, e.id)),
          el(
            'span',
            `${sentence(ends)}. ${directionWords(ends)}.${standing ? ` ${standing}.` : ''}`,
            'status-text',
          ),
        );
        row.append(
          text,
          button(`Read ${e.name} in the panel`, () => pick({ kind: 'edge', id: e.id }), {
            variant: 'secondary',
          }),
        );
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

      listPane.append(listing);

      // The moved nodes wait for a save.
      const moved = new Map<string, { x: number; y: number }>();
      let current = web.layout as Layout;
      let seed = web.layout_seed;
      let labels = true;
      let focusOn = false;
      let selected: { kind: 'node' | 'edge'; id: string } | null = null;
      const selectedBox = el('div', '', 'stack');
      const showSelected = () => {
        selectedBox.replaceChildren();
        if (!selected) {
          selectedBox.append(empty('Select an entry or a relationship to read it here.'));
          return;
        }
        if (selected.kind === 'edge') {
          const e = graph.edges.find((x) => x.id === selected?.id);
          if (!e) return;
          const ends = { endA: e.end_a.name, endB: e.end_b.name, oneWay: e.one_way };
          const detail = el('div', '', 'stack');
          selectedBox.append(
            el('h2', e.name, 'group-title'),
            el('p', `${sentence(ends)}. ${directionWords(ends)}.`, 'status-text'),
            detail,
            link('Open the relationship', relationshipHref(tenant, e.id)),
          );
          const asked = e.id;
          void relationshipPanel(tenant, e, shellOf()).then((filled) => {
            // The selection may have moved on while this was read.
            if (selected?.id === asked) detail.replaceChildren(filled);
          });
          return;
        }
        const node = model.nodes.find((n) => n.id === selected?.id);
        selectedBox.append(
          el('h2', node?.name ?? '', 'group-title'),
          link('Open its page', entryHref(tenant, selected.id)),
        );
        const around = graph.edges.filter(
          (e) => e.end_a.id === selected?.id || e.end_b.id === selected?.id,
        );
        const items = el('ul', '', 'list');
        items.setAttribute('aria-label', 'Its relationships');
        for (const e of around) {
          const row = el('li');
          row.append(link(e.name, relationshipHref(tenant, e.id)));
          items.append(row);
        }
        selectedBox.append(
          around.length ? items : empty('No relationship in this web ties it to another entry.'),
        );
        // In the hand-placed layout a writer gives a position by number, as well as by drag or by keys.
        if (manage && current === 'manual' && drawing) {
          const at = drawing.positionOf(selected.id);
          const nodeId = selected.id;
          const x = field('X', at ? String(Math.round(at.x * 10) / 10) : '', 'number');
          const y = field('Y', at ? String(Math.round(at.y * 10) / 10) : '', 'number');
          const apply = () => {
            const nx = Number(x.input.value);
            const ny = Number(y.input.value);
            if (x.input.value !== '' && y.input.value !== '' && Number.isFinite(nx + ny)) {
              drawing?.place(nodeId, { x: nx, y: ny });
            }
          };
          x.input.addEventListener('change', apply);
          y.input.addEventListener('change', apply);
          selectedBox.append(
            el('h3', 'Place it by hand', 'group-title'),
            x.label,
            y.label,
            el(
              'p',
              'Drag it, or hold Alt and press an arrow key (Shift for a bigger step).',
              'status-text',
            ),
          );
        }
        const asked = selected.id;
        void membersPanel(tenant, asked).then((group) => {
          if (group && selected?.id === asked) selectedBox.append(group);
        });
      };
      let steps = 0;
      let hullsOn = false;
      let groups: GraphGroup[] = [];
      /** What is drawn: within some steps of the selection, with Focus dimming the rest, and the groups. */
      const composed = (): GraphModel => {
        let nodes = [...model.nodes];
        let edges = [...model.edges];
        const ends = (): string[] => {
          if (!selected) return [];
          if (selected.kind === 'node') return [selected.id];
          const e = model.edges.find((x) => x.id === selected?.id);
          return e ? [e.a, e.b] : [];
        };
        if (steps > 0 && ends().length) {
          const within = new Set(ends());
          for (let hop = 0; hop < steps; hop += 1) {
            for (const e of model.edges) {
              if (within.has(e.a) || within.has(e.b)) {
                within.add(e.a);
                within.add(e.b);
              }
            }
          }
          nodes = nodes.filter((n) => within.has(n.id));
          edges = edges.filter((e) => within.has(e.a) && within.has(e.b));
        }
        let keep: Set<string> | null = null;
        if (focusOn && selected) {
          keep = new Set<string>(ends());
          for (const e of model.edges) {
            if (selected.kind === 'node' && (e.a === selected.id || e.b === selected.id)) {
              keep.add(e.a);
              keep.add(e.b);
            }
          }
        }
        return {
          nodes: nodes.map((n) => ({ ...n, dim: keep ? !keep.has(n.id) : false })),
          edges,
          groups: hullsOn ? groups : [],
        };
      };
      const applyFocus = () => {
        if (!drawing) return;
        drawing.setModel(composed());
        // Radial draws outwards from the selected entry (SO7).
        if (current === 'radial') {
          drawing.setView({ focus: selected?.kind === 'node' ? selected.id : null });
        }
      };
      pick = (choice) => {
        selected = choice;
        mark(choice.kind === 'edge' ? choice.id : null);
        drawing?.select(choice);
        showSelected();
        applyFocus();
        openTab('selected');
      };
      if (!tooBig && model.nodes.length > 0) {
        drawing = createGraphView(hostBox, {
          model,
          title: web.name,
          iconBase: `${BRANDING_CSS_URL}/icons.svg`,
          themeHint: web.theme_hint ?? null,
          view: { layout: current as LayoutName, seed, positions, labels },
          onSelect: (selection) => {
            selected = selection;
            mark(selection?.kind === 'edge' ? selection.id : null);
            showSelected();
            applyFocus();
            if (selection) openTab('selected');
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
        const events = eventChooser(tenant, 'As of this Event');
        const readers = entryPicker(tenant, 'Read as this entry (what it may read)', {
          kind: 'being',
        });
        const apply = async () => {
          remember();
          await draw();
        };
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
          ['', 'The web\u2019s own'],
          ...Object.keys(THEMES).map((t): [string, string] => [
            t,
            t === 'family' ? 'Family tree' : 'Default',
          ]),
        ],
        '',
      );
      themes.input.addEventListener('change', () => drawing?.setTheme(themes.input.value || null));
      layout.input.addEventListener('change', () => {
        current = layout.input.value as Layout;
        drawing?.setView({
          layout: current as LayoutName,
          focus: current === 'radial' && selected?.kind === 'node' ? selected.id : null,
        });
      });
      seeded.input.addEventListener('change', () => {
        seed = Math.max(0, Math.floor(Number(seeded.input.value) || 0));
        drawing?.setView({ seed });
      });
      // The standing the lines show (weight and label); saved with how the web is drawn.
      const shownSelect = select(
        'Standing shown on the lines',
        [['', 'None'], ...numbers.map((x): [string, string] => [x.id, x.name])],
        shown?.id ?? '',
      );
      controls.body.append(layout.label, seeded.label, themes.label, shownSelect.label);
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
                standing_stat_id: shownSelect.input.value || null,
                as_of_event: lens.asOf,
              });
              state.version = saved.version;
              say(status, 'Saved how it is drawn.');
              // A different standing on the lines is read again, which draws the web afresh.
              if ((shownSelect.input.value || null) !== (shown?.id ?? null)) {
                shellOf()?.toast({ kind: 'ok', title: 'Saved how it is drawn' });
                await draw();
              }
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
      // The panel: what is selected, how it is drawn, the lenses, the members and the notes.
      type Tab = 'selected' | 'drawing' | 'lens' | 'types' | 'notes';
      const panes: [Tab, string, HTMLElement][] = [
        ['selected', 'Selected', selectedBox],
        ['drawing', 'Drawing', controls.root],
        ['lens', 'Date and reader', lensControls()],
        ...(manage
          ? [
              ['types', 'Types', editor(tenant, id, version, graph, web, draw)] as [
                Tab,
                string,
                HTMLElement,
              ],
            ]
          : []),
        ['notes', 'Notes', notes(tenant, id)],
      ];
      const panelHead = el('div', '', 'row');
      const panelTitle = el('h2', '', 'group-title grow');
      const panelBody = el('div', '', 'stack');
      const closePanel = button(
        'Close the panel',
        () => {
          panelTab = null;
          panel.hidden = true;
          view.dataset.panel = 'closed';
          for (const chip of bar.querySelectorAll('button[data-tab]')) {
            chip.setAttribute('aria-pressed', 'false');
          }
        },
        { variant: 'secondary' },
      );
      panelHead.append(panelTitle, closePanel);
      panel.append(panelHead, panelBody);
      function openTab(tab: Tab) {
        const found = panes.find(([name]) => name === tab);
        if (!found) return;
        panelTab = tab;
        panelTitle.textContent = found[1];
        panelBody.replaceChildren(found[2]);
        panel.hidden = false;
        view.dataset.panel = 'open';
        // On a phone the panel follows the bar down the page: bring it into view.
        if (matchMedia('(max-width: 720px)').matches) panel.scrollIntoView({ block: 'nearest' });
        for (const chip of bar.querySelectorAll('button[data-tab]')) {
          chip.setAttribute('aria-pressed', String(chip.getAttribute('data-tab') === tab));
        }
      }
      showSelected();

      // The vertical bar of region switches (SO7), each a chip with its word.
      const bar = floatBar;
      const chip = (name: string, iconName: string, run: (self: HTMLButtonElement) => void) => {
        const node = el('button', '', 'btn btn-secondary web-chip');
        node.type = 'button';
        node.append(icon(iconName), document.createTextNode(name));
        node.addEventListener('click', () => run(node));
        return node;
      };
      const toggleChip = (name: string, iconName: string, on: (value: boolean) => void) => {
        const node = chip(name, iconName, (self) => {
          const next = self.getAttribute('aria-pressed') !== 'true';
          self.setAttribute('aria-pressed', String(next));
          on(next);
        });
        node.setAttribute('aria-pressed', 'false');
        return node;
      };
      const labelsChip = toggleChip('Labels', 'eye', (value) => {
        labels = value;
        drawing?.setView({ labels });
      });
      labelsChip.setAttribute('aria-pressed', 'true');
      const focusChip = toggleChip('Focus', 'focus-mode', (value) => {
        focusOn = value;
        if (value && !selected) {
          say(status, 'Focus needs a selection: select an entry or a relationship first.');
        }
        applyFocus();
      });
      // A lens is a switch: on says so and a second press clears it; off opens its controls.
      const lensChip = (name: string, iconName: string, on: boolean, clear: () => void) => {
        const node = chip(name, iconName, () => {
          if (!on) {
            openTab('lens');
            return;
          }
          clear();
          remember();
          void draw();
        });
        node.setAttribute('aria-pressed', String(on));
        return node;
      };
      const groupsChip = toggleChip('Groups', 'social', (value) => {
        hullsOn = value;
        drawing?.setView({ hulls: value });
        if (value && groups.length === 0) {
          void loadGroups(
            tenant,
            graph.members.map((m) => m.entry.id),
          ).then((found) => {
            groups = found;
            if (found.length === 0) say(status, 'No group has two members in this web.');
            applyFocus();
          });
        } else applyFocus();
      });
      const stepsChip = chip('Steps: All', 'kind-relationship', (self) => {
        if (!selected) {
          say(
            status,
            'Steps are counted from a selection: select an entry or a relationship first.',
          );
          return;
        }
        steps = (steps + 1) % 3;
        self.textContent = '';
        self.append(
          icon('kind-relationship'),
          document.createTextNode(steps ? `Steps: ${steps}` : 'Steps: All'),
        );
        self.setAttribute('aria-pressed', String(steps > 0));
        applyFocus();
      });
      stepsChip.setAttribute('aria-pressed', 'false');
      const tabChip = (tab: Tab, name: string, iconName: string) => {
        const node = chip(name, iconName, () => openTab(tab));
        node.dataset.tab = tab;
        node.setAttribute('aria-pressed', 'false');
        return node;
      };
      bar.append(
        labelsChip,
        groupsChip,
        stepsChip,
        focusChip,
        tabChip('drawing', 'Drawing', 'settings'),
        lensChip('As of an Event', 'kind-clock', Boolean(lens.asOf), () => {
          lens.asOf = null;
        }),
        lensChip('As read by', 'eye', Boolean(lens.asSeenBy), () => {
          lens.asSeenBy = null;
        }),
        ...(manage ? [tabChip('types', 'Types', 'filter')] : []),
        ...(manage
          ? [
              chip('Members', 'kind-being', () => {
                void openMembers({
                  tenant,
                  id,
                  selected:
                    selected?.kind === 'node'
                      ? {
                          id: selected.id,
                          name: model.nodes.find((n) => n.id === selected?.id)?.name ?? '',
                        }
                      : null,
                  changed: draw,
                });
              }),
            ]
          : []),
        chip('Connect', 'kind-relationship', () => {
          const form = relationshipForm(tenant, manage);
          void formDialog({
            title: 'Connect two entries',
            submit: 'Make the relationship',
            fields: form.fields,
            async run() {
              const made = await form.submit();
              if (manage) {
                const have = new Set(graph.members.map((m) => m.entry.id));
                const missing = made.ends.filter((e) => !have.has(e.id));
                if (missing.length) {
                  const { version: now } = await readWeb(tenant, id);
                  await writeMembers(tenant, id, now, {
                    set: missing.map((e) => ({ entry_id: e.id })),
                  });
                }
              }
              await draw();
            },
          });
        }),
        tabChip('notes', 'Notes', 'kind-fact'),
      );

      floatZoom.append(
        button('Zoom in', () => drawing?.zoomIn()),
        button('Zoom out', () => drawing?.zoomOut()),
        button('Fit', () => drawing?.fit()),
      );

      // The legend says what a line is (identity.md section 18).
      const legend = el('div', '', 'graph-legend');
      legend.append(
        el('span', 'Solid: direct'),
        el('span', 'Dashed: through others'),
        el('span', 'Dotted: unknown'),
      );
      floatLegend.prepend(legend);

      // Graph, Matrix and List are three views of one web (SO2); the view is in the address. On a
      // phone the matrix is one entry's standings as a list, and is called so.
      const asked = new URLSearchParams(location.search).get('view');
      const wanted: 'graph' | 'matrix' | 'list' =
        asked === 'list' || asked === 'matrix' ? asked : 'graph';
      const phone = matchMedia('(max-width: 720px)').matches;
      const switcher = el('div', '', 'segmented-control');
      switcher.setAttribute('role', 'group');
      switcher.setAttribute('aria-label', 'View');
      let matrixDrawn = false;
      let matrixHandle: { carry(entries: string[]): void } | null = null;
      // What is selected, as the entries the matrix can mark: an entry, or the two ends of a relationship.
      const selectedEntries = (): string[] => {
        if (!selected) return [];
        if (selected.kind === 'node') return [selected.id];
        const e = model.edges.find((x) => x.id === selected?.id);
        return e ? [e.a, e.b] : [];
      };
      const showView = (name: 'graph' | 'matrix' | 'list') => {
        graphPane.hidden = name !== 'graph';
        matrixPane.hidden = name !== 'matrix';
        listPane.hidden = name !== 'list';
        floatZoom.hidden = name !== 'graph';
        // Labels and Focus are about the drawing only.
        labelsChip.hidden = name !== 'graph';
        groupsChip.hidden = name !== 'graph';
        stepsChip.hidden = name !== 'graph';
        focusChip.hidden = name !== 'graph';
        view.dataset.view = name;
        if (name === 'matrix' && !matrixDrawn) {
          matrixDrawn = true;
          void import('./matrix-view')
            .then((m) =>
              m.renderMatrix(matrixPane, tenant, id, {
                asOf: lens.asOf,
                asOfName,
                asSeenBy: lens.asSeenBy,
              }),
            )
            .then((handle) => {
              matrixHandle = handle;
              handle?.carry(selectedEntries());
            });
        } else if (name === 'matrix') matrixHandle?.carry(selectedEntries());
        for (const b of switcher.querySelectorAll('button')) {
          b.setAttribute('aria-pressed', String(b.dataset.view === name));
        }
        const next = new URLSearchParams(location.search);
        if (name === 'graph') next.delete('view');
        else next.set('view', name);
        history.replaceState(null, '', `${location.pathname}?${next}`);
      };
      for (const [name, text] of [
        ['graph', 'Graph'],
        ['matrix', phone ? 'Standings' : 'Matrix'],
        ['list', 'List'],
      ] as const) {
        const b = el('button', text);
        b.type = 'button';
        b.dataset.view = name;
        b.addEventListener('click', () => showView(name));
        switcher.append(b);
      }
      floatHead.append(el('div', '', 'row-tight'));
      floatHead.lastElementChild?.append(switcher);
      showView(wanted);
      host.replaceChildren(view);
      if (panelTab) openTab(panelTab as Tab);
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
  _graph: Awaited<ReturnType<typeof readGraph>>,
  web: Awaited<ReturnType<typeof readWeb>>['web'],
  redraw: () => Promise<void>,
) {
  const section = el('section', '', 'stack');
  section.append(sectionHead('Types shown'));
  const status = statusLine();

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
  section.append(types.root, status);
  return section;
}
